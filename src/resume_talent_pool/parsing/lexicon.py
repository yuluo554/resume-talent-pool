"""技能/证书词典（M2 解析资源，冻结自 data/generator_specs/skills.json）。

用途（仅两处，防口径漂移）：
1. 无分隔符长串的切分兜底——STSong-Light CID 字体中 U+00B7（·）零宽，
   skill_sep=· 的 PDF 抽取后技能行熔断为无分隔长串（M2 全量实测 18/71 份），
   词典最长匹配切分是唯一恢复手段；切出的每个片段仍是原文连续子串
   （熔断=原样拼接），防幻觉口径不破；
2. 分隔符切分后的邻接重并——HTML/CSS 含 /，与 skill_sep=/ 天然歧义，
   "HTML"+"/"+"CSS" 命中词典即还原为一个标签。

纪律：词典只用于**已渲染文本的切分**，不得引入原文不存在的值（不会造成
"蒙分"式 FP）；参数池改动时须同步再生本文件（tests/test_parsing_slots.py
有一致性防漂移测试）。
"""

SKILLS = frozenset({
    "C语言", "Docker", "Elasticsearch", "Excel",
    "Flink", "Git", "HTML/CSS", "Hive",
    "JMeter", "Java", "JavaScript", "Kafka",
    "Kubernetes", "Linux", "MongoDB", "MyBatis",
    "MySQL", "Nginx", "Office办公软件", "PPT",
    "Pandas", "Python", "Python爬虫", "RabbitMQ",
    "React", "Redis", "SPSS", "Selenium",
    "Shell", "Spark", "Spring Boot", "Spring Cloud",
    "Vue", "Word", "会议组织", "公文写作",
    "办公自动化", "发票管理", "员工入离职办理", "固定资产盘点",
    "基础会计", "微服务", "成本核算", "报表编制",
    "招聘渠道维护", "数据结构", "机器学习", "档案管理",
    "社保公积金办理", "税务申报", "考勤统计", "自动化测试",
    "薪酬核算", "财务核算", "预算管理",
})

CERTIFICATES = frozenset({
    "C1驾驶证", "CET-4", "CET-6", "PMP",
    "中级会计职称", "人力资源管理师三级", "初级会计职称", "初级经济师",
    "普通话二级甲等", "计算机三级", "计算机二级", "软考中级（软件设计师）",
    "软考高级（系统分析师）",
})
