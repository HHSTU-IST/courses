#!/usr/bin/env python3
"""考研 408 长线备考计划 - plan.json 生成器（按月精度, monthly granularity）

目标：90+ / 150（良好）
周期：2026-09-30 ~ 2027-03-30（182 天 / 26 周 / 6 个月）
预算：工作日 240 min，周末 120 min
"""

import json
import os
from datetime import date, timedelta

PLAN_ID = "plan-408"
ROOT = os.path.dirname(os.path.abspath(__file__))
PLAN_DIR = os.path.join(ROOT, PLAN_ID)

START = date(2026, 9, 30)
DEADLINE = date(2027, 3, 30)
WEEKDAY_BUDGET = 240
WEEKEND_BUDGET = 120

# ── 26 周内容表 ────────────────────────────────────────────────
# (wk, ds_read, ds_code, ds_feynman, co, os_, net, milestone)
WEEKS = [
    (
        1,
        "线性表复盘：顺序表 / 单链表 / 静态链表",
        "顺序表 + 单链表的增删改查（含头插 / 尾插 / 按位删除）",
        "顺序表和链表各自的代价是什么，什么时候用哪个",
        "第 1 章 计算机系统概述",
        "第 1 章 操作系统概述",
        "第 1 章 计算机网络体系结构",
        "单链表增删查改能脱稿写出",
    ),
    (
        2,
        "双链表、循环链表 + 栈与队列（顺序 / 链式）",
        "栈实现中缀转后缀 + 后缀求值；循环队列",
        "栈和队列，用数组和链表各实现一遍有什么差别",
        "第 2 章 数据的表示和运算",
        "第 2 章 进程与线程（状态、调度）",
        "第 2 章 物理层",
        "中缀转后缀 + 表达式求值独立写出",
    ),
    (
        3,
        "树与二叉树：性质、存储结构、三种遍历 + 层次遍历",
        "二叉树前序 / 中序 / 后序（递归 + 非递归）+ 层次遍历",
        "为什么前序 + 中序能唯一还原一棵二叉树，前序 + 后序不行",
        "第 3 章 存储系统（上：层次结构、Cache、主存）",
        "第 2 章 同步与互斥（信号量、经典同步问题）",
        "第 3 章 数据链路层（上：组帧、差错控制、流量控制）",
        "三种遍历 + 层次遍历手写不出错",
    ),
    (
        4,
        "线索二叉树、树与森林、BST、AVL、哈夫曼树",
        "BST 增删查 + AVL 四种旋转 + 哈夫曼编码构造",
        "AVL 的旋转是怎么把树高压回 O(log n) 的",
        "第 3 章 存储系统（下：虚拟存储、磁盘）",
        "第 3 章 内存管理（上：分页、分段）",
        "第 3 章 数据链路层（下：介质访问控制、以太网、交换机）",
        "AVL 四种旋转手写不断链",
    ),
    (
        5,
        "堆与优先队列、并查集 + 树章节综合题",
        "堆的上浮 / 下沉 + 建堆 + 并查集（路径压缩 + 按秩合并）",
        "把「树」这一章从二叉树讲到哈夫曼，脱稿 20 分钟",
        "第 4 章 指令系统",
        "第 4 章 文件管理",
        "第 4 章 网络层（上：IP、子网划分）",
        "树章节选择题 ≥ 70%；本月复盘",
    ),
    (
        6,
        "图：邻接矩阵 / 邻接表、BFS / DFS、生成树",
        "邻接表建图 + BFS / DFS（递归 + 非递归）+ 连通分量计数",
        "BFS 和 DFS 各自适合解决哪类问题，各举三个例子",
        "第 5 章 中央处理器（上：CPU 结构、指令周期）",
        "第 3 章 内存管理（下：页面置换、地址变换）",
        "第 4 章 网络层（下：路由算法、ARP / ICMP）",
        "BFS / DFS 手写并能统计连通分量",
    ),
    (
        7,
        "图的应用：最小生成树、最短路径、拓扑排序、关键路径",
        "Prim / Kruskal + Dijkstra / Floyd",
        "为什么 Dijkstra 处理不了负权边，Floyd 却可以",
        "第 5 章 中央处理器（下：流水线、冒险与冲突）",
        "第 2 章 死锁（检测、避免、银行家算法）",
        "第 5 章 传输层（上：UDP、TCP 连接管理）",
        "四个图算法能默写",
    ),
    (
        8,
        "查找：顺序 / 折半 / 分块、B 树与 B+ 树、散列表",
        "折半查找 + 散列表（线性探测 / 链地址法）",
        "B 树和 B+ 树差在哪，为什么数据库索引偏爱 B+ 树",
        "第 6 章 总线",
        "第 5 章 输入 / 输出管理",
        "第 5 章 传输层（下：TCP 流量控制、拥塞控制）",
        "查找章节选择题 ≥ 70%",
    ),
    (
        9,
        "排序（一）：直接插入、希尔、冒泡、快排、简单选择、堆排序",
        "快速排序（含随机化）+ 堆排序",
        "快排最坏会退化成什么、怎么规避；为什么它仍是最快的通用排序",
        "第 7 章 输入 / 输出系统",
        "基础期串讲：OS 全科框架",
        "第 6 章 应用层（上：DNS、HTTP、FTP）",
        "六种排序手写 + 复杂度 / 稳定性对照表默写",
    ),
    (
        10,
        "排序（二）：归并、基数、外部排序",
        "归并排序（递归 + 迭代）+ 基数排序；外部排序归并趟数计算",
        "外部排序的归并趟数怎么算，为什么要多路归并",
        "基础期总复盘（错题 + 框架默写）",
        "基础期总复盘",
        "第 6 章 应用层（下）+ 基础期总复盘",
        "408 基础期全科过完；数据结构选择题 ≥ 65%",
    ),
    (
        11,
        "真题分类：线性表 + 栈队列 + 树（选择 + 综合）",
        "近 10 年真题大题暴力解手写（每次限时 25 min）",
        "把本周每道错题用一句话说清错在哪",
        "真题分类：第 1–3 章",
        "真题分类：第 1–2 章",
        "真题分类：第 1–3 章",
        "数据结构选择题 ≥ 75%",
    ),
    (
        12,
        "真题分类：图 + 查找 + 排序",
        "真题图算法大题手写（MST / 最短路各 2 道）",
        "图的四个算法，各挑一道真题讲一遍",
        "真题分类：第 4–5 章",
        "真题分类：第 3 章",
        "真题分类：第 4 章",
        "数据结构综合题正确率 ≥ 70%",
    ),
    (
        13,
        "算法大题专项：暴力解 → 结构化 → 优化（每年 2 道，共 45 分）",
        "每日 1 道真题大题，限时 25 min，写完对照答案改",
        "把我的解法讲给一个完全不会的人听",
        "真题分类：第 6–7 章",
        "真题分类：第 4–5 章",
        "真题分类：第 5–6 章",
        "算法大题稳定拿到 10 / 15 分",
    ),
    (
        14,
        "算法大题专项 + 跨年全科串讲",
        "错题重写 ≥ 10 道",
        "数据结构全科串讲，脱稿 1 小时",
        "计组全科框架默写",
        "OS 全科框架默写",
        "计网全科框架默写",
        "四科知识框架图完成",
    ),
    (
        15,
        "真题回溯 2015–2019（分类重做）",
        "每日 1 道大题 + 1 道算法题",
        "排序算法的稳定性与复杂度，闭眼讲一遍",
        "计组真题 2015–2019",
        "OS 真题 2015–2019",
        "计网真题 2015–2019",
        "单科正确率 ≥ 70%",
    ),
    (
        16,
        "弱项建档：按错题统计定向补漏",
        "按弱项清单定制 10 道手写题",
        "把最弱的 3 个知识点讲透",
        "计组弱项建档",
        "OS 弱项建档",
        "计网弱项建档",
        "四科弱项清单完成",
    ),
    (
        17,
        "真题 2020–2025 分类",
        "每日 1 道大题，限时 25 min",
        "错题归因表：概念不清 / 算错 / 漏条件，各占多少",
        "计组真题 2020–2025",
        "OS 真题 2020–2025",
        "计网真题 2020–2025",
        "成套模拟 ≥ 85 / 150",
    ),
    (
        18,
        "算法题提速模板整理",
        "模板默写 5 遍（每遍限时 12 min）",
        "我的算法大题答题模板，讲一遍",
        "计组公式速查整理",
        "OS 计算题模板整理",
        "计网协议栈串讲",
        "答题模板固化",
    ),
    (
        19,
        "春节周：每日 1 套模拟（或半套）+ 精析",
        "算法保底策略整理（先写暴力解拿分）",
        "把数据结构讲给家人听",
        "模拟 1 套 + 精析",
        "模拟 1 套 + 精析",
        "模拟 1 套 + 精析",
        "模拟 ≥ 90 / 150",
    ),
    (
        20,
        "模拟 2 套 + 算法保底策略固化",
        "暴力解模板熟练（限时 15 min 写出）",
        "我的保底策略：哪些题先跳过、哪些必拿",
        "模拟 2 套",
        "模拟 2 套",
        "模拟 2 套",
        "算法保底分 ≥ 10 / 15",
    ),
    (
        21,
        "模拟 2 套 + 选择题提速",
        "每日 1 道大题限时 20 min",
        "四科知识框架默写讲一遍",
        "模拟 2 套 + 提速",
        "模拟 2 套 + 提速",
        "模拟 2 套 + 提速",
        "选择题 30 min 内完成",
    ),
    (
        22,
        "模拟 2 套 + 大题答题规范",
        "算法题步骤书写规范化（伪代码 + 注释 + 复杂度）",
        "答题卡上我会怎么写，讲一遍",
        "模拟 2 套 + 步骤规范",
        "模拟 2 套 + 步骤规范",
        "模拟 2 套 + 步骤规范",
        "大题步骤分拿满",
    ),
    (
        23,
        "全科知识框架默写 + 模拟 1 套",
        "错题重写 ≥ 8 道",
        "知识框架默写讲一遍",
        "框架默写",
        "框架默写",
        "框架默写",
        "知识框架完整度 ≥ 90%",
    ),
    (
        24,
        "弱项定向突破 + 模拟 1 套",
        "弱项定制题手写",
        "最后 3 个薄弱知识点讲透",
        "弱项突破",
        "弱项突破",
        "弱项突破",
        "弱项正确率 ≥ 70%",
    ),
    (
        25,
        "综合模拟 2 套 + 心态调整",
        "算法速解模板默写",
        "整套卷子讲给自己听",
        "模拟 2 套",
        "模拟 2 套",
        "模拟 2 套",
        "模拟稳定 ≥ 95 / 150",
    ),
    (
        26,
        "考前收官：错题本清空 + 隔天 1 套保温",
        "算法模板最后默写 1 遍",
        "考前 3 天：只讲不学",
        "公式速查",
        "算法 / 调度速查",
        "协议速查",
        "自信上考场",
    ),
]


def week_range(w):
    """返回该周的 (start_date, end_date)。W1 为 5 天启动周，W26 为 9 天收尾周。"""
    if w == 1:
        return date(2026, 9, 30), date(2026, 10, 4)
    if w == 26:
        return date(2027, 3, 22), date(2027, 3, 30)
    s = date(2026, 10, 5) + timedelta(days=7 * (w - 2))
    return s, s + timedelta(days=6)


def stage_of(w):
    if w <= 10:
        return "stage-1"
    if w <= 18:
        return "stage-2"
    return "stage-3"


STAGES = [
    {
        "id": "stage-1",
        "name": "基础期（M1–M2 / W1–W10）",
        "duration_days": 68,
        "goals": [
            "数据结构从零到能做题：线性表 → 栈队列 → 树 → 图 → 查找 → 排序 全章过一遍",
            "计组第 1–5 章、OS 第 1–5 章、计网第 1–6 章教材精读完成",
            "每周固定产出 1 个可运行代码实现 + 1 次费曼输出",
        ],
    },
    {
        "id": "stage-2",
        "name": "强化期（M3–M4 / W11–W18）",
        "duration_days": 56,
        "goals": [
            "408 真题按知识点分类刷完一轮（含 2015–2025）",
            "数据结构算法大题专项突破：暴力解稳定 ≥ 10 / 15 分",
            "四科弱项建档 + 定向补漏",
        ],
    },
    {
        "id": "stage-3",
        "name": "冲刺期（M5–M6 / W19–W26）",
        "duration_days": 58,
        "goals": [
            "每周 2 套完整模拟 + 逐题精析，分数稳定 ≥ 95 / 150",
            "全科知识框架默写完整度 ≥ 90%",
            "算法大题保底策略固化，考前 3 天转保温",
        ],
    },
]

TASK_META = {
    "ds_read": ("reading", "教材精读 + 笔记，本节概念合上书能口述"),
    "ds_code": ("output", "费曼 + 重做：写不出就是没学会，写完讲一遍逻辑"),
    "co": ("reading", "帕累托：先抓高频考点（Cache / 流水线 / 浮点数）"),
    "os": ("reading", "帕累托：先抓高频考点（PV 操作 / 页面置换 / 文件索引）"),
    "net": ("reading", "帕累托：先抓高频考点（TCP 状态机 / 子网划分 / CSMA/CD）"),
    "review": ("review", "艾宾浩斯：今日内容 D-1 复现一遍，讲不清的记入错题本"),
    "feynman": ("output", "费曼法：讲给一个不懂的人听，卡住的地方就是没学会"),
    "weekly_review": ("review", "艾宾浩斯 D-7：回看本周错题，能 1 分钟讲明白才算过"),
}


def mk(tid, title, dur, key, priority="medium"):
    cat, tip = TASK_META[key]
    return {
        "id": tid,
        "title": title,
        "duration_min": dur,
        "category": cat,
        "checkable": True,
        "priority": priority,
        "methodology_tip": tip,
    }


def build_daily():
    out = []
    for w, ds_read, ds_code, ds_feynman, co, os_, net, _ms in WEEKS:
        s, e = week_range(w)
        sid = stage_of(w)
        d = s
        while d <= e:
            is_weekend = d.weekday() >= 5
            if is_weekend:
                # 周末 120 min = 代码实现 45 + 费曼输出 45 + 周复盘 30
                tasks = [
                    mk("t-001", f"[W{w} 代码] {ds_code}", 45, "ds_code", "high"),
                    mk("t-002", f"[W{w} 费曼] {ds_feynman}", 45, "feynman", "high"),
                    mk(
                        "t-003",
                        f"[W{w} 复盘] 错题本 + 本周内容 D-7 复现",
                        30,
                        "weekly_review",
                        "high",
                    ),
                ]
            else:
                # 工作日 240 min = DS 90 + 计组 45 + OS 45 + 计网 45 + 复盘 15
                tasks = [
                    mk("t-001", f"[W{w}] 数据结构：{ds_read}", 45, "ds_read", "high"),
                    mk(
                        "t-002",
                        f"[W{w}] 数据结构：{ds_code}（手写 / 调试）",
                        45,
                        "ds_code",
                        "high",
                    ),
                    mk("t-003", f"[W{w}] 计组：{co}", 45, "co"),
                    mk("t-004", f"[W{w}] 操作系统：{os_}", 45, "os"),
                    mk("t-005", f"[W{w}] 计算机网络：{net}", 45, "net"),
                    mk("t-006", "睡前复现今日重点 + 明日任务清单", 15, "review"),
                ]
            assert sum(t["duration_min"] for t in tasks) == (
                WEEKEND_BUDGET if is_weekend else WEEKDAY_BUDGET
            )
            out.append(
                {
                    "date": d.isoformat(),
                    "stage_id": sid,
                    "week": w,
                    "day_type": "weekend" if is_weekend else "weekday",
                    "tasks": tasks,
                }
            )
            d += timedelta(days=1)
    return out


def build_month_views():
    """按月视图：6 个月，每月含周列表。"""
    months = [
        (1, "2026-09-30 ~ 2026-11-01", [1, 2, 3, 4, 5], "数据结构打底：线性表 → 树"),
        (
            2,
            "2026-11-02 ~ 2026-12-06",
            [6, 7, 8, 9, 10],
            "图 + 查找 + 排序，四科第一遍收口",
        ),
        (
            3,
            "2026-12-07 ~ 2027-01-03",
            [11, 12, 13, 14],
            "408 真题分类刷 + 算法大题专项",
        ),
        (4, "2027-01-04 ~ 2027-01-31", [15, 16, 17, 18], "全科真题 + 弱项建档补强"),
        (5, "2027-02-01 ~ 2027-02-28", [19, 20, 21, 22], "全科模拟 + 框架巩固"),
        (6, "2027-03-01 ~ 2027-03-30", [23, 24, 25, 26], "冲刺模考 + 状态保温"),
    ]
    by_wk = {w[0]: w for w in WEEKS}
    out = []
    for mid, rng, wks, theme in months:
        weeks = []
        for w in wks:
            rec = by_wk[w]
            s, e = week_range(w)
            weeks.append(
                {
                    "week": w,
                    "date_range": f"{s.month}/{s.day}–{e.month}/{e.day}",
                    "ds": rec[1],
                    "ds_code": rec[2],
                    "ds_feynman": rec[3],
                    "co": rec[4],
                    "os": rec[5],
                    "net": rec[6],
                    "milestone": rec[7],
                }
            )
        out.append({"month": mid, "date_range": rng, "theme": theme, "weeks": weeks})
    return out


def main():
    daily = build_daily()
    plan = {
        "id": PLAN_ID,
        "version": 1,
        "meta": {
            "title": "考研 408 长线备考计划（零基础 → 90+）",
            "goal": "408 计算机学科专业基础综合 90+ / 150（良好）",
            "deadline": DEADLINE.isoformat(),
            "current_level": "数据结构零基础（树 / 图 / 排序 / 查找完全没看），线性表 / 栈队列大概了解；"
            "计组与操作系统了解基本概念；计算机网络只看过一点",
            "daily_budget": {"weekday": WEEKDAY_BUDGET, "weekend": WEEKEND_BUDGET},
            "weak_points": [
                "数据结构（零基础）",
                "计算机网络（只看过一点）",
                "数据结构算法大题（45 分的拉分项）",
            ],
            "resources": [
                "王道《数据结构》",
                "王道《计算机组成原理》",
                "王道《操作系统》",
                "王道《计算机网络》",
                "严蔚敏《数据结构（C 语言版）》",
                "408 历年真题（2010–2025）",
            ],
            "methodology": ["ebbinghaus", "pomodoro", "pareto", "feynman"],
            "template_origin": "kaoyan",
            "time_granularity": "monthly",
            "_calendar_note": {
                "start_date": START.isoformat(),
                "plan_end_date": DEADLINE.isoformat(),
                "deadline": DEADLINE.isoformat(),
                "buffer_days": 0,
                "deadline_overridden": False,
                "tip": "计划完整覆盖至 2027-03-30（含当日）",
            },
        },
        "stages": STAGES,
        "month_views": build_month_views(),
        "daily_tasks": daily,
    }
    os.makedirs(PLAN_DIR, exist_ok=True)
    with open(os.path.join(PLAN_DIR, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    for name, payload in (
        ("checkin-log.json", {"plan_id": PLAN_ID, "checkins": []}),
        (
            "streak.json",
            {
                "plan_id": PLAN_ID,
                "current": 0,
                "longest": 0,
                "last_checkin": None,
                "broken_dates": [],
                "milestones_unlocked": [],
                "achievements": [],
            },
        ),
        (
            "user-config.json",
            {
                "persona": "gentle-senior",
                "active_plan_id": PLAN_ID,
                "checkin_channel": "daily",
                "reminder_time": "08:00",
            },
        ),
    ):
        with open(os.path.join(PLAN_DIR, name), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # ── NEVER 2 自检：逐日对账 ──
    bad = []
    for d in daily:
        budget = WEEKEND_BUDGET if d["day_type"] == "weekend" else WEEKDAY_BUDGET
        total = sum(t["duration_min"] for t in d["tasks"])
        if total != budget:
            bad.append((d["date"], total, budget))
    print(f"plan.json -> {os.path.join(PLAN_DIR, 'plan.json')}")
    print(f"days={len(daily)}  tasks={sum(len(d['tasks']) for d in daily)}")
    print(
        f"weekday_count={sum(1 for d in daily if d['day_type'] == 'weekday')}  "
        f"weekend_count={sum(1 for d in daily if d['day_type'] == 'weekend')}"
    )
    print(f"budget_mismatch={len(bad)}")
    if bad:
        print(bad[:5])


if __name__ == "__main__":
    main()
