"""TalentStore：本地人才库（M3）。

SQLite（标准库 sqlite3）业务表 + FTS5 trigram 全文检索（本机 sqlite 3.34.0 实测可用，
D-009/D-023）。表结构定稿自 plan/04 §5 草案，M3 落地增量：
- FTS 内容同步走**应用层双写**（候选人每次合并后整行重建 candidates_fts），不用触发器
  ——trigram + 合并重建路径简单可测，触发器难以覆盖"合并回填"语义（D-023）；
- trigram 分词对 <3 字符查询无命中（三字元窗口），search() 对短查询退化为
  LIKE 兜底（候选表/经历表/标签表直接扫描，本地库规模小，可接受）；
- tags.kind 在草案 skill|source|custom 基础上增加 certificate（证书标签随版本累积）。
- merge_conflicts.field='candidate_merge' 表示"待人工确认的候选人合并"
  （option_a=既有候选人 id，option_b=新建候选人 id，status='pending'）。

M5 增量：settings 读写与脱敏开关（mask_pii，默认开，plan/04 §6）；screening_cards()
为 JD 初筛供卡（主档字段+全部经历+技能标签，CLI screen 与 GUI 初筛页共用）；
导入原件副本目录 imports/ 落在库文件同级（pipeline 拷贝，purge 一键清除删除）。

库文件默认位置 %APPDATA%/resume-talent-pool/talent.db（D-015，非 Windows 退回
~/.resume-talent-pool/）；file_sha256 UNIQUE 兼做导入去重。
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.card import CandidateCard, Experience, FieldValue
from ..normalize import matcher, merge

DEFAULT_DB_DIRNAME = "resume-talent-pool"
DB_FILENAME = "talent.db"
IMPORTS_DIRNAME = "imports"

# settings 表键：脱敏显示开关（"1"=开，默认开；"0"=关）。显示层与导出同受约束（plan/04 §6）。
MASK_SETTING_KEY = "mask_pii"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  name_py TEXT NOT NULL DEFAULT '',
  phone TEXT,
  email TEXT,
  degree TEXT,
  school TEXT,
  major TEXT,
  graduation_date TEXT,
  desired_position TEXT,
  latest_resume_id INTEGER,
  years_of_work REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resumes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  source_file TEXT NOT NULL,
  file_type TEXT NOT NULL,
  file_sha256 TEXT NOT NULL UNIQUE,
  resume_date TEXT,
  card_json TEXT NOT NULL,
  parsed_at TEXT
);
CREATE TABLE IF NOT EXISTS experiences(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  resume_id INTEGER NOT NULL REFERENCES resumes(id),
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  company TEXT,
  title TEXT,
  start_month TEXT,
  end_month TEXT
);
CREATE TABLE IF NOT EXISTS tags(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_tags(
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  tag_id INTEGER NOT NULL REFERENCES tags(id),
  PRIMARY KEY(candidate_id, tag_id)
);
CREATE TABLE IF NOT EXISTS merge_conflicts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  field TEXT NOT NULL,
  option_a TEXT,
  option_b TEXT,
  chosen TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS jd_requirements(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  condition_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""

_FTS_DDL = ("CREATE VIRTUAL TABLE IF NOT EXISTS candidates_fts USING fts5("
            "candidate_id UNINDEXED, name, skills, school, major, company, "
            "tokenize='trigram')")

_CANDIDATE_COLS = ("name", "phone", "email", "degree", "school", "major",
                   "graduation_date", "desired_position")


def default_db_path() -> Path:
    """默认库路径：%APPDATA%/resume-talent-pool/talent.db（D-015）；
    非 Windows（APPDATA 未设）退回家目录隐藏目录。"""
    base = os.environ.get("APPDATA")
    root = Path(base) / DEFAULT_DB_DIRNAME if base else Path.home() / ("." + DEFAULT_DB_DIRNAME)
    return root / DB_FILENAME


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _content_sha(card: CandidateCard) -> str:
    """无文件 sha（测试直造参数卡）时的兜底：按卡片内容派生，同卡去重语义不变。"""
    digest = hashlib.sha256()
    digest.update(card.source_file.encode("utf-8"))
    digest.update(json.dumps(card.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class TalentStore:
    """本地人才库：导入归一建档/并入、FTS 检索、时间线、冲突确认。"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(_SCHEMA)
        try:
            self.conn.execute(_FTS_DDL)
        except sqlite3.OperationalError as exc:
            self.conn.close()
            raise RuntimeError(
                f"当前 SQLite 不支持 FTS5 trigram 全文索引（{exc}）。"
                "需要 sqlite >= 3.34，或按 plan/06 D-009 改用 2-gram 预分词双写。") from exc
        self.conn.commit()

    # -- 生命周期 ----------------------------------------------------------

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "TalentStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- 导入归一 ----------------------------------------------------------

    def has_sha256(self, file_sha256: str) -> bool:
        if not file_sha256:
            return False
        row = self.conn.execute("SELECT 1 FROM resumes WHERE file_sha256=?",
                                (file_sha256,)).fetchone()
        return row is not None

    def add_parsed_card(self, card: CandidateCard) -> Dict[str, Any]:
        """归一判定后建档/并入/登记冲突。

        返回 {"status": new|merged|manual_review|duplicate, "candidate_id",
        "resume_id", "matched_candidate_id"?, "score"?, "conflicts"?}。
        """
        sha = card.file_sha256 or _content_sha(card)   # 无文件 sha（测试直造卡）按内容派生
        if self.has_sha256(sha):
            row = self.conn.execute(
                "SELECT id, candidate_id FROM resumes WHERE file_sha256=?",
                (sha,)).fetchone()
            return {"status": "duplicate", "candidate_id": row["candidate_id"],
                    "resume_id": row["id"]}

        best = self._best_match(card)
        if best is not None and best[0]["decision"] == "auto_merge":
            pair, cand_row, cand_card = best
            return self._merge_into(card, cand_row, cand_card, pair, sha)
        if best is not None and best[0]["decision"] == "manual_review":
            pair, cand_row, _ = best
            result = self._new_candidate(card, sha)
            self._record_merge_review(cand_row["id"], result["candidate_id"], pair["score"])
            result.update({"status": "manual_review", "matched_candidate_id": cand_row["id"],
                           "score": pair["score"]})
            return result
        return self._new_candidate(card, sha)

    def _candidate_card(self, candidate_id: int, row: sqlite3.Row = None) -> CandidateCard:
        """候选人主档 → 参与两两判定的伪参数卡（主档字段 + 全部经历）。

        parsed_at 取该候选人已导入简历的最新解析时间——伪卡代表"截至当前的合并态"，
        freshness_key（plan/04 §3.3 最新版本判定）据此与乱序导入的旧简历比较。
        """
        if row is None:
            row = self.conn.execute("SELECT * FROM candidates WHERE id=?",
                                    (candidate_id,)).fetchone()
            if row is None:
                raise ValueError(f"候选人不存在: {candidate_id}")
        fields = {key: FieldValue(value=row[key]) for key in _CANDIDATE_COLS
                  if row[key] is not None}
        exps = [Experience(company=r["company"], title=r["title"],
                           start=r["start_month"], end=r["end_month"])
                for r in self.conn.execute(
                    "SELECT company, title, start_month, end_month FROM experiences "
                    "WHERE candidate_id=? ORDER BY start_month", (candidate_id,))]
        parsed = [r["parsed_at"] for r in self.conn.execute(
            "SELECT parsed_at FROM resumes WHERE candidate_id=? AND parsed_at IS NOT NULL",
            (candidate_id,))]
        return CandidateCard(source_file=f"candidate:{candidate_id}", file_type="profile",
                             fields=fields, experiences=exps,
                             parsed_at=max(parsed) if parsed else "")

    def _best_match(self, card: CandidateCard):
        """遍历既有候选人（键1/键2 通路在 decide_pair 内判定），取综合分最高的非不同人。"""
        best = None
        for row in self.conn.execute("SELECT * FROM candidates ORDER BY id"):
            cand_card = self._candidate_card(row["id"], row)
            pair = merge.decide_pair(card, cand_card)
            if pair["decision"] == "different_person":
                continue
            if best is None or pair["score"] > best[0]["score"]:
                best = (pair, row, cand_card)
        return best

    def _new_candidate(self, card: CandidateCard, sha: str = "") -> Dict[str, Any]:
        now = _now()
        f = matcher.field_values(card)
        name = _text(f.get("name")) or "(无名)"
        py = sorted(matcher.pinyin_keys(name))
        cur = self.conn.execute(
            "INSERT INTO candidates(name, name_py, phone, email, degree, school, major,"
            " graduation_date, desired_position, years_of_work, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, " ".join(py), matcher.normalize_phone(f.get("phone")) or None,
             matcher.normalize_email(f.get("email")) or None,
             _text(f.get("degree")), _text(f.get("school")), _text(f.get("major")),
             _text(f.get("graduation_date")), _text(f.get("desired_position")),
             matcher.work_span_years(card.experiences), now, now))
        candidate_id = cur.lastrowid
        resume_id = self._insert_resume(card, candidate_id, sha)
        self.conn.execute("UPDATE candidates SET latest_resume_id=? WHERE id=?",
                          (resume_id, candidate_id))
        self._insert_experiences(card, candidate_id, resume_id)
        self._attach_tags(card, candidate_id)
        self._rebuild_fts(candidate_id)
        self.conn.commit()
        return {"status": "new", "candidate_id": candidate_id, "resume_id": resume_id}

    def _merge_into(self, card: CandidateCard, cand_row: sqlite3.Row,
                    cand_card: CandidateCard, pair: Dict[str, Any], sha: str) -> Dict[str, Any]:
        candidate_id = cand_row["id"]
        now = _now()
        conflicts = merge.conflict_fields(card, cand_card)
        resume_id = self._insert_resume(card, candidate_id, sha)
        self._insert_experiences(card, candidate_id, resume_id)
        self._attach_tags(card, candidate_id)

        f = matcher.field_values(card)
        old = matcher.field_values(cand_card)

        # 字段取值：按简历时间取最新版本（plan/04 §3.3）；乱序导入旧简历不覆盖新值。
        incoming_newer = merge.is_newer(card, cand_card)

        def pick(field: str, incoming: Any) -> Any:
            if incoming_newer:
                return merge.merged_scalar(cand_row[field], incoming)  # 新版本赢，缺失回填
            return cand_row[field] if cand_row[field] is not None else incoming

        name = _text(f.get("name"))
        py = sorted(matcher.pinyin_keys(name or cand_row["name"]))
        self.conn.execute(
            "UPDATE candidates SET name=?, name_py=?, phone=?, email=?, degree=?, school=?,"
            " major=?, graduation_date=?, desired_position=?, latest_resume_id=?,"
            " years_of_work=?, updated_at=? WHERE id=?",
            (pick("name", name), " ".join(py),
             pick("phone", matcher.normalize_phone(f.get("phone")) or None),
             pick("email", matcher.normalize_email(f.get("email")) or None),
             pick("degree", _text(f.get("degree"))),
             pick("school", _text(f.get("school"))),
             pick("major", _text(f.get("major"))),
             pick("graduation_date", _text(f.get("graduation_date"))),
             pick("desired_position", _text(f.get("desired_position"))),
             resume_id if incoming_newer else cand_row["latest_resume_id"],
             self._recompute_years(candidate_id),
             now, candidate_id))
        for field in conflicts:
            self.conn.execute(
                "INSERT INTO merge_conflicts(candidate_id, field, option_a, option_b,"
                " status, created_at) VALUES(?,?,?,?,?,?)",
                (candidate_id, field, _text(old.get(field)), _text(f.get(field)),
                 "pending", now))
        self._rebuild_fts(candidate_id)
        self.conn.commit()
        return {"status": "merged", "candidate_id": candidate_id, "resume_id": resume_id,
                "matched_candidate_id": candidate_id, "score": pair["score"],
                "conflicts": conflicts}

    def _record_merge_review(self, existing_id: int, new_id: int, score: float) -> None:
        self.conn.execute(
            "INSERT INTO merge_conflicts(candidate_id, field, option_a, option_b,"
            " status, created_at) VALUES(?,?,?,?,?,?)",
            (existing_id, "candidate_merge", str(existing_id), str(new_id),
             "pending", _now()))
        self.conn.commit()

    def _insert_resume(self, card: CandidateCard, candidate_id: int, sha: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO resumes(candidate_id, source_file, file_type, file_sha256,"
            " resume_date, card_json, parsed_at) VALUES(?,?,?,?,?,?,?)",
            (candidate_id, card.source_file, card.file_type, sha,
             self._resume_date(card),
             json.dumps(card.to_dict(), ensure_ascii=False), card.parsed_at))
        return cur.lastrowid

    @staticmethod
    def _resume_date(card: CandidateCard) -> str:
        """简历时间 = 最新经历端点（开放端记 TIME_HORIZON）；无经历退 parsed_at 月份。"""
        best_point, best_idx = "", -1
        for exp in card.experiences:
            point = exp.end or (matcher.TIME_HORIZON if exp.start else None)
            if not point:
                continue
            idx = matcher.month_index(point)
            if idx > best_idx:
                best_point, best_idx = point, idx
        if best_point:
            return best_point
        return card.parsed_at[:7] if card.parsed_at else ""

    def _insert_experiences(self, card: CandidateCard, candidate_id: int, resume_id: int) -> None:
        for exp in card.experiences:
            self.conn.execute(
                "INSERT INTO experiences(resume_id, candidate_id, company, title,"
                " start_month, end_month) VALUES(?,?,?,?,?,?)",
                (resume_id, candidate_id, exp.company, exp.title, exp.start, exp.end))

    def _attach_tags(self, card: CandidateCard, candidate_id: int) -> None:
        for kind, items in (("skill", card.skills), ("certificate", card.certificates)):
            for item in items:
                name = _text(item.value)
                if not name:
                    continue
                self.conn.execute("INSERT OR IGNORE INTO tags(name, kind) VALUES(?,?)",
                                  (name, kind))
                tag_id = self.conn.execute("SELECT id FROM tags WHERE name=?",
                                           (name,)).fetchone()["id"]
                self.conn.execute(
                    "INSERT OR IGNORE INTO candidate_tags(candidate_id, tag_id) VALUES(?,?)",
                    (candidate_id, tag_id))

    def _recompute_years(self, candidate_id: int) -> float:
        exps = [Experience(company=r["company"], title=r["title"],
                           start=r["start_month"], end=r["end_month"])
                for r in self.conn.execute(
                    "SELECT company, title, start_month, end_month FROM experiences"
                    " WHERE candidate_id=?", (candidate_id,))]
        return matcher.work_span_years(exps)

    def _rebuild_fts(self, candidate_id: int) -> None:
        row = self.conn.execute("SELECT * FROM candidates WHERE id=?",
                                (candidate_id,)).fetchone()
        skills = [r["name"] for r in self.conn.execute(
            "SELECT t.name FROM tags t JOIN candidate_tags ct ON ct.tag_id=t.id"
            " WHERE ct.candidate_id=? AND t.kind='skill' ORDER BY t.name", (candidate_id,))]
        companies = [r["company"] for r in self.conn.execute(
            "SELECT DISTINCT company FROM experiences WHERE candidate_id=? AND company"
            " IS NOT NULL ORDER BY company", (candidate_id,))]
        self.conn.execute("DELETE FROM candidates_fts WHERE candidate_id=?", (candidate_id,))
        self.conn.execute(
            "INSERT INTO candidates_fts(candidate_id, name, skills, school, major, company)"
            " VALUES(?,?,?,?,?,?)",
            (candidate_id, row["name"], " ".join(skills), row["school"] or "",
             row["major"] or "", " ".join(companies)))

    # -- 检索与视图 ----------------------------------------------------------

    def search(self, query: str, filters: dict = None) -> List[Dict[str, Any]]:
        """FTS5 全文检索（≥3 字符走 trigram，短查询 LIKE 兜底）+ 多维筛选。

        filters: degree（精确）/ skill（标签等值，大小写不敏感）/ min_years（>=）/
        limit（默认 50）。返回按年限降序的候选人字典列表。
        """
        filters = filters or {}
        ids = None
        q = (query or "").strip()
        if q:
            if len(q) >= 3:
                rows = self.conn.execute(
                    "SELECT candidate_id FROM candidates_fts WHERE candidates_fts MATCH ?",
                    ('"' + q.replace('"', '""') + '"',)).fetchall()
                ids = [r["candidate_id"] for r in rows]
            else:
                like = f"%{q}%"
                rows = self.conn.execute(
                    "SELECT DISTINCT c.id AS candidate_id FROM candidates c"
                    " WHERE c.name LIKE ? OR c.school LIKE ? OR c.major LIKE ?"
                    " OR c.desired_position LIKE ?"
                    " OR EXISTS(SELECT 1 FROM experiences e WHERE e.candidate_id=c.id"
                    "   AND e.company LIKE ?)"
                    " OR EXISTS(SELECT 1 FROM candidate_tags ct JOIN tags t"
                    "   ON t.id=ct.tag_id WHERE ct.candidate_id=c.id AND t.name LIKE ?)",
                    (like, like, like, like, like, like)).fetchall()
                ids = [r["candidate_id"] for r in rows]
            if not ids:
                return []

        where, params = [], []
        if ids is not None:
            where.append("c.id IN (%s)" % ",".join("?" * len(ids)))
            params.extend(ids)
        if filters.get("degree"):
            where.append("c.degree = ?")
            params.append(filters["degree"])
        if filters.get("skill"):
            where.append("EXISTS(SELECT 1 FROM candidate_tags ct JOIN tags t"
                         " ON t.id=ct.tag_id WHERE ct.candidate_id=c.id"
                         " AND t.name = ? COLLATE NOCASE)")
            params.append(str(filters["skill"]).strip())
        if filters.get("min_years") is not None:
            where.append("c.years_of_work >= ?")
            params.append(float(filters["min_years"]))

        sql = "SELECT c.* FROM candidates c"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY c.years_of_work DESC, c.id"
        limit = int(filters.get("limit") or 50)
        sql += " LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.conn.execute(sql, params)]

    def candidate(self, candidate_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute("SELECT * FROM candidates WHERE id=?",
                                (candidate_id,)).fetchone()
        return dict(row) if row else None

    def timeline(self, candidate_id: int) -> Dict[str, Any]:
        """候选人时间线：主档 + 按简历时间排序的多版本简历 + 逐版本经历 + 技能/证书标签。"""
        cand = self.candidate(candidate_id)
        if cand is None:
            raise ValueError(f"候选人不存在: {candidate_id}")
        resumes = [dict(r) for r in self.conn.execute(
            "SELECT id, source_file, file_type, resume_date, parsed_at FROM resumes"
            " WHERE candidate_id=? ORDER BY resume_date, id", (candidate_id,))]
        experiences = [dict(r) for r in self.conn.execute(
            "SELECT resume_id, company, title, start_month, end_month FROM experiences"
            " WHERE candidate_id=? ORDER BY resume_id, start_month", (candidate_id,))]
        tags = [dict(r) for r in self.conn.execute(
            "SELECT t.name, t.kind FROM tags t JOIN candidate_tags ct ON ct.tag_id=t.id"
            " WHERE ct.candidate_id=? ORDER BY t.kind, t.name", (candidate_id,))]
        return {"candidate": cand, "resumes": resumes,
                "experiences": experiences, "tags": tags}

    # -- 冲突确认 ----------------------------------------------------------

    def pending_reviews(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM merge_conflicts WHERE status='pending' ORDER BY id")]

    def resolve_conflict(self, conflict_id: int, chosen: str) -> bool:
        cur = self.conn.execute(
            "UPDATE merge_conflicts SET chosen=?, status='resolved', resolved_at=?"
            " WHERE id=? AND status='pending'",
            (chosen, _now(), conflict_id))
        self.conn.commit()
        return cur.rowcount > 0

    def resolve_field_conflict(self, conflict_id: int, chosen: str) -> bool:
        """字段冲突人工采纳：把 chosen 值写入候选人主档并关闭冲突记录。

        chosen 为 option_a/option_b 之一（GUI 面板按钮传入）；写入即生效（显示层
        下次刷新可见），不删除任何历史简历归档。
        """
        row = self.conn.execute("SELECT * FROM merge_conflicts WHERE id=?",
                                (conflict_id,)).fetchone()
        if row is None or row["status"] != "pending" or row["field"] == "candidate_merge":
            return False
        if chosen not in (row["option_a"], row["option_b"]):
            return False
        self.conn.execute(f"UPDATE candidates SET {row['field']}=? WHERE id=?",
                          (chosen, row["candidate_id"]))
        self.conn.commit()
        return self.resolve_conflict(conflict_id, chosen)

    def merge_candidates(self, source_id: int, target_id: int) -> Dict[str, Any]:
        """candidate_merge 待确认记录的人工确认闭环：把 source 并入 target。

        简历/经历/标签/待确认记录全部迁移到 target；主档字段按最新版本取值
        （merge.is_newer，与自动合并 _merge_into 同口径）；删除 source 档。
        返回 {"moved_resumes", "conflicts"}。source 不存在或与 target 相同抛 ValueError。
        """
        if source_id == target_id:
            raise ValueError("source 与 target 为同一候选人")
        src = self.candidate(source_id)
        tgt = self.candidate(target_id)
        if src is None or tgt is None:
            raise ValueError(f"候选人不存在: {source_id or target_id}")

        src_card = self._candidate_card(source_id)
        tgt_card = self._candidate_card(target_id)
        source_newer = merge.is_newer(src_card, tgt_card)

        moved = self.conn.execute(
            "UPDATE resumes SET candidate_id=? WHERE candidate_id=?",
            (target_id, source_id)).rowcount
        self.conn.execute("UPDATE experiences SET candidate_id=? WHERE candidate_id=?",
                          (target_id, source_id))
        self.conn.execute(
            "INSERT OR IGNORE INTO candidate_tags(candidate_id, tag_id)"
            " SELECT ?, tag_id FROM candidate_tags WHERE candidate_id=?",
            (target_id, source_id))
        self.conn.execute("UPDATE merge_conflicts SET candidate_id=? WHERE candidate_id=?",
                          (target_id, source_id))

        # 字段取值：最新版本赢，历史值回填（与自动合并 pick 语义一致，plan/04 §3.3）
        for col in _CANDIDATE_COLS:
            if source_newer:
                value = merge.merged_scalar(tgt[col], src[col])
            else:
                value = tgt[col] if tgt[col] is not None else src[col]
            self.conn.execute(f"UPDATE candidates SET {col}=? WHERE id=?",
                              (value, target_id))
        py = sorted(matcher.pinyin_keys(self.candidate(target_id)["name"] or ""))
        self.conn.execute("UPDATE candidates SET name_py=?, latest_resume_id=?,"
                          " years_of_work=? WHERE id=?",
                          (" ".join(py),
                           self.conn.execute(
                               "SELECT latest_resume_id FROM candidates WHERE id=?",
                               (target_id,)).fetchone()["latest_resume_id"],
                           self._recompute_years(target_id), target_id))
        self.conn.execute("DELETE FROM candidates WHERE id=?", (source_id,))
        self._rebuild_fts(target_id)
        self.conn.commit()
        return {"moved_resumes": moved}

    # -- 设置与隐私 ----------------------------------------------------------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)))
        self.conn.commit()

    def masking_enabled(self) -> bool:
        """脱敏开关（settings.mask_pii，缺省=开，plan/04 §6）。"""
        return self.get_setting(MASK_SETTING_KEY, "1") != "0"

    def set_masking_enabled(self, enabled: bool) -> None:
        self.set_setting(MASK_SETTING_KEY, "1" if enabled else "0")

    # -- JD 初筛输入 ---------------------------------------------------------

    def screening_cards(self) -> List[Dict[str, Any]]:
        """全部候选人的初筛输入：[{"candidate_id", "card"}]（id 升序，确定性）。

        参数卡 = 主档字段 + 全部经历 + 技能标签（screening.jd 纯函数通路的输入，
        与 GUI 初筛页、CLI screen 共用）。
        """
        out = []
        for row in self.conn.execute("SELECT id FROM candidates ORDER BY id"):
            candidate_id = row["id"]
            card = self._candidate_card(candidate_id)
            skills = [r["name"] for r in self.conn.execute(
                "SELECT t.name FROM tags t JOIN candidate_tags ct ON ct.tag_id=t.id"
                " WHERE ct.candidate_id=? AND t.kind='skill' ORDER BY t.name",
                (candidate_id,))]
            card.skills = [FieldValue(value=s) for s in skills]
            out.append({"candidate_id": candidate_id, "card": card})
        return out
