#!/usr/bin/env python3
"""
知识复利引擎 v3.0 — 记忆存储、检索、分析和管理脚本

命令：
  store    保存一条记忆
  recall   检索相关记忆
  list     列出最近记忆
  search   搜索记忆
  delete   删除记忆
  export   导出记忆为 Markdown
  cleanup  清理长期未访问的记忆
  stats    记忆库统计
  dashboard 可视化仪表盘
  weekly   生成周报
  relation 发现记忆之间的关联
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict

MEMORY_DIR = Path(__file__).parent.parent / ".knowledge-compound"
MEMORY_FILE = MEMORY_DIR / "memory-bank.json"

TYPE_LABELS = {
    "preference": "偏好",
    "decision": "决策",
    "project": "项目背景",
    "lesson": "经验教训",
    "fact": "知识点",
}

TYPE_ICONS = {
    "preference": "🎯",
    "decision": "✅",
    "project": "📦",
    "lesson": "💡",
    "fact": "📖",
}


def _ensure_memory_file():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        _write_memories([])


def _read_memories():
    _ensure_memory_file()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _write_memories(memories):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)


def _next_id(memories):
    ids = [m["id"] for m in memories if "id" in m]
    nums = [int(mid.replace("mem_", "")) for mid in ids if mid.startswith("mem_")]
    return f"mem_{max(nums) + 1:03d}" if nums else "mem_001"


def _is_duplicate(memories, content, threshold=0.85):
    for m in memories:
        if _similarity(m["content"], content) >= threshold:
            return True, m["id"]
    return False, None


def _similarity(a, b):
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0
    a_words, b_words = set(a.split()), set(b.split())
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    return len(intersection) / max(len(a_words), len(b_words))


def _discover_relations(memories):
    relations = []
    for i, a in enumerate(memories):
        for j, b in enumerate(memories):
            if j <= i:
                continue
            score = 0
            a_words = set(a.get("content", "").lower().split())
            b_words = set(b.get("content", "").lower().split())
            word_overlap = a_words & b_words
            if len(word_overlap) >= 3:
                score += len(word_overlap)
            a_tags = set(t.lower() for t in a.get("tags", []))
            b_tags = set(t.lower() for t in b.get("tags", []))
            tag_overlap = a_tags & b_tags
            if tag_overlap:
                score += len(tag_overlap) * 2
            if a.get("type") == "project" or b.get("type") == "project":
                shared = word_overlap - {"这个", "项目", "一个", "的", "了", "是", "我", "用"}
                if len(shared) >= 2:
                    score += 2
            common_words = word_overlap - {"这个", "项目", "一个", "的", "了", "是", "我", "用", "在", "有", "和", "就", "也", "都", "要", "会", "可以", "因为", "所以", "但是", "如果"}
            if len(common_words) >= 2:
                score += 1
            if score >= 3:
                relations.append({
                    "id_a": a["id"],
                    "id_b": b["id"],
                    "content_a": a["content"],
                    "content_b": b["content"],
                    "strength": min(score / 5, 1.0),
                    "common_words": list(common_words),
                })
    relations.sort(key=lambda r: -r["strength"])
    return relations


def _knowledge_compound_index(memories):
    if not memories:
        return 0, 0
    total = len(memories)
    relations = _discover_relations(memories)
    relation_score = min(len(relations) * 5, 30)
    diversity = len(set(m.get("type", "unknown") for m in memories)) * 5
    access_total = sum(m.get("access_count", 0) for m in memories)
    access_score = min(access_total / total * 2, 20)
    kci = min(relation_score + diversity + access_score + 10, 100)
    saved_hours = round(access_total * 0.05, 1)
    return kci, saved_hours


def _stars_from_score(score):
    if score >= 80:
        return "★★★★★"
    elif score >= 60:
        return "★★★★☆"
    elif score >= 40:
        return "★★★☆☆"
    elif score >= 20:
        return "★★☆☆☆"
    else:
        return "★☆☆☆☆"


def cmd_store(args):
    if not args.content:
        print("错误：请提供要记忆的内容")
        return
    memories = _read_memories()
    is_dup, dup_id = _is_duplicate(memories, args.content)
    if is_dup:
        for m in memories:
            if m["id"] == dup_id:
                m["last_accessed"] = date.today().isoformat()
                m["access_count"] = m.get("access_count", 0) + 1
                _write_memories(memories)
                print(f"记忆已更新（去重，原记忆 {dup_id} 访问次数+1）")
                return
    mem = {
        "id": _next_id(memories),
        "type": args.type or "fact",
        "content": args.content.strip(),
        "context": args.context or "",
        "tags": args.tags.split(",") if args.tags else [],
        "created": date.today().isoformat(),
        "last_accessed": date.today().isoformat(),
        "access_count": 1,
    }
    memories.append(mem)
    _write_memories(memories)
    new_relations = _discover_relations(memories)
    print(f"记忆已保存：{mem['id']} ({TYPE_LABELS.get(mem['type'], mem['type'])})")
    fresh_rels = [r for r in new_relations if r["id_a"] == mem["id"] or r["id_b"] == mem["id"]]
    if fresh_rels:
        print(f"🔗 发现 {len(fresh_rels)} 条关联：")
        for r in fresh_rels[:3]:
            other = r["content_b"] if r["id_a"] == mem["id"] else r["content_a"]
            print(f"   关联到「{other[:40]}...」")


def cmd_recall(args):
    query = args.content or ""
    if not query.strip():
        memories = _read_memories()
        if memories:
            memories.sort(key=lambda m: (m.get("access_count", 0), m.get("last_accessed", "")), reverse=True)
            results = memories[: args.limit or 5]
            print(f"活跃记忆（共 {len(memories)} 条）：\n")
            for m in results:
                icon = TYPE_ICONS.get(m.get("type", ""), "📌")
                print(f"  {icon} [{m['id']}] {m['content']}")
                if m.get("context"):
                    print(f"      上下文：{m['context']}")
                tags_str = ", ".join(m.get("tags", []))
                if tags_str:
                    print(f"      标签：{tags_str}")
                print(f"      引用 {m.get('access_count', 0)} 次 | 记录于 {m['created']}")
                print()
            return
        print("提示：请提供关键词来检索相关记忆")
        return
    memories = _read_memories()
    query_lower = query.lower()
    query_words = set(query_lower.split())
    scored = []
    for m in memories:
        score = 0
        content_lower = m.get("content", "").lower()
        context_lower = m.get("context", "").lower()
        tags_lower = [t.lower() for t in m.get("tags", [])]
        if query_lower in content_lower or query_lower in context_lower:
            score += 3
        for w in query_words:
            if w in content_lower:
                score += 2
            if w in context_lower:
                score += 1
            if w in tags_lower:
                score += 2
        if m.get("access_count", 0) > 5:
            score += 1
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: -x[0])
    results = scored[: args.limit or 5]
    if not results:
        print(f"未找到与「{query}」相关的记忆")
        return
    print(f"找到 {len(results)} 条相关记忆：\n")
    for score, m in results:
        icon = TYPE_ICONS.get(m.get("type", ""), "📌")
        print(f"  {icon} [{m['id']}] ({TYPE_LABELS.get(m['type'], m['type'])}) {m['content']}")
        if m.get("context"):
            print(f"      上下文：{m['context']}")
        tags_str = ", ".join(m.get("tags", []))
        if tags_str:
            print(f"      标签：{tags_str}")
        print(f"      记录于 {m['created']}，已被引用 {m.get('access_count', 0)} 次")
        print()
        m["last_accessed"] = date.today().isoformat()
        m["access_count"] = m.get("access_count", 0) + 1
    _write_memories(memories)


def cmd_list(args):
    memories = _read_memories()
    if not memories:
        print("还没有任何记忆。开始聊天吧，我会自动记住重要信息。")
        return
    memories.sort(key=lambda m: m.get("last_accessed", ""), reverse=True)
    limit = args.limit or 10
    shown = memories[:limit]
    print(f"最近 {len(shown)} 条记忆（共 {len(memories)} 条）：\n")
    for m in shown:
        icon = TYPE_ICONS.get(m.get("type", ""), "📌")
        tags_str = ", ".join(m.get("tags", [])) if m.get("tags") else ""
        tag_info = f" [{tags_str}]" if tags_str else ""
        print(f"  {icon} [{m['id']}] ({TYPE_LABELS.get(m['type'], m['type'])}) {m['content']}{tag_info}")
        print(f"      记录于 {m['created']}，上次访问 {m.get('last_accessed', '未知')}")
        print()


def cmd_search(args):
    cmd_recall(args)


def cmd_delete(args):
    if not args.content:
        print("错误：请提供要删除的记忆 ID")
        return
    mem_id = args.content.strip()
    memories = _read_memories()
    before = len(memories)
    memories = [m for m in memories if m["id"] != mem_id]
    if len(memories) == before:
        print(f"未找到记忆：{mem_id}")
        return
    _write_memories(memories)
    print(f"记忆 {mem_id} 已删除")


def cmd_export(args):
    memories = _read_memories()
    if not memories:
        print("还没有任何记忆可导出。")
        return
    today = date.today().isoformat()
    export_path = MEMORY_DIR / f"memory-export-{today}.md"
    lines = [
        f"# 知识复利引擎 - 记忆导出",
        f"导出日期：{today}",
        f"记忆总数：{len(memories)}",
        "",
        "---",
        "",
    ]
    for m in memories:
        icon = TYPE_ICONS.get(m.get("type", ""), "📌")
        lines.append(f"## {icon} [{m['id']}] ({TYPE_LABELS.get(m['type'], m['type'])})")
        lines.append(f"")
        lines.append(f"**内容**：{m['content']}")
        if m.get("context"):
            lines.append(f"**上下文**：{m['context']}")
        tags_str = ", ".join(m.get("tags", [])) if m.get("tags") else "无"
        lines.append(f"**标签**：{tags_str}")
        lines.append(f"**记录时间**：{m['created']}")
        lines.append(f"**引用次数**：{m.get('access_count', 0)}")
        lines.append(f"")
    with open(export_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"记忆已导出到：{export_path}")


def cmd_cleanup(args):
    memories = _read_memories()
    before = len(memories)
    kept = []
    cutoff = datetime.now().timestamp() - 90 * 86400
    for m in memories:
        try:
            last_acc = datetime.strptime(m.get("last_accessed", ""), "%Y-%m-%d").timestamp()
        except (ValueError, TypeError):
            last_acc = 0
        if last_acc >= cutoff or m.get("access_count", 0) > 2:
            kept.append(m)
    _write_memories(kept)
    removed = before - len(kept)
    print(f"清理完成：移除了 {removed} 条长期未访问的记忆，剩余 {len(kept)} 条活跃记忆")


def cmd_stats(args):
    memories = _read_memories()
    if not memories:
        print("记忆库为空。")
        return
    type_counts = defaultdict(int)
    for m in memories:
        t = m.get("type", "unknown")
        type_counts[t] += 1
    total = len(memories)
    avg_access = sum(m.get("access_count", 0) for m in memories) / total
    print(f"📊 记忆库统计")
    print(f"  {'='*30}")
    print(f"  总记忆数：{total}")
    print(f"  按类型：")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        label = TYPE_LABELS.get(t, t)
        icon = TYPE_ICONS.get(t, "📌")
        pct = c / total * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"    {icon} {label}: {c} 条 {bar}")
    print(f"  平均引用次数：{avg_access:.1f}")
    print(f"  存储位置：{MEMORY_FILE}")


def cmd_dashboard(args):
    memories = _read_memories()
    if not memories:
        print("记忆库为空。开始使用吧，我会自动记住重要信息！")
        return
    total = len(memories)
    type_counts = defaultdict(int)
    for m in memories:
        type_counts[m.get("type", "unknown")] += 1
    relations = _discover_relations(memories)
    total_relations = len(relations)
    total_access = sum(m.get("access_count", 0) for m in memories)
    avg_access = total_access / total
    kci, saved_hours = _knowledge_compound_index(memories)
    stars = _stars_from_score(kci)
    print(f"╔{'═'*35}╗")
    print(f"║   知识复利引擎 · 仪表盘{' ' * 13}║")
    print(f"╠{'═'*35}╣")
    print(f"║  🧠 记忆总数       {total:>4} 条{' ' * 12}║")
    for t in ["preference", "decision", "project", "lesson", "fact"]:
        c = type_counts.get(t, 0)
        label = TYPE_LABELS.get(t, t)
        icon = TYPE_ICONS.get(t, "📌")
        bar = "█" * min(c, 20) + "░" * max(0, 20 - min(c, 20))
        short_bar = bar[:min(c, 30) or 1]
        print(f"║  {icon} {label:<8s} {c:>4} 条 {short_bar}{' ' * 4}║")
    print(f"║{' ' * 35}║")
    print(f"║  🔗 关联发现       {total_relations:>4} 组{' ' * 12}║")
    print(f"║  📈 知识复利指数   {stars}{' ' * (18 - len(stars))}║")
    print(f"║  ⏱ 节省重复解释 ≈ {saved_hours:>4.1f}h{' ' * 12}║")
    print(f"╚{'═'*35}╝")
    if total_relations > 0:
        print(f"\n🔗 最强关联 TOP 3：")
        for r in relations[:3]:
            print(f"  · 「{r['content_a'][:28]}...」")
            print(f"    ↔ 「{r['content_b'][:28]}...」")
    print(f"\n📊 记忆类型分布：")
    for t in ["preference", "decision", "project", "lesson", "fact"]:
        c = type_counts.get(t, 0)
        if c > 0:
            label = TYPE_LABELS.get(t, t)
            icon = TYPE_ICONS.get(t, "📌")
            pct = c / total * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"  {icon} {label:<8s} {bar} {c}条 ({pct:.0f}%)")


def cmd_weekly(args):
    memories = _read_memories()
    if not memories:
        print("记忆库为空，无法生成周报。")
        return
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()
    new_this_week = [m for m in memories if m.get("created", "") >= week_ago]
    accessed_this_week = [m for m in memories if m.get("last_accessed", "") >= week_ago]
    total = len(memories)
    total_access = sum(m.get("access_count", 0) for m in memories)
    kci, saved_hours = _knowledge_compound_index(memories)
    stars = _stars_from_score(kci)
    type_counts = defaultdict(int)
    for m in new_this_week:
        type_counts[m.get("type", "unknown")] += 1
    relations = _discover_relations(memories)
    report_path = MEMORY_DIR / f"weekly-{today.isoformat()}.md"
    lines = [
        f"# 📊 知识复利引擎 · 周报",
        f"",
        f"> 报告周期：{week_ago} ~ {today.isoformat()}",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"---",
        f"",
        f"## 📈 本周概览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 记忆总数 | {total} 条 |",
        f"| 本周新增 | {len(new_this_week)} 条 |",
        f"| 本周引用 | {len(accessed_this_week)} 条被访问 |",
        f"| 关联发现 | {len(relations)} 组 |",
        f"| 知识复利指数 | {stars} ({kci}/100) |",
        f"| 累计节省时间 | ≈ {saved_hours}h |",
        f"",
    ]
    if new_this_week:
        lines.append(f"## 🆕 本周新增记忆")
        lines.append(f"")
        for t in ["preference", "decision", "project", "lesson", "fact"]:
            c = type_counts.get(t, 0)
            if c > 0:
                label = TYPE_LABELS.get(t, t)
                icon = TYPE_ICONS.get(t, "📌")
                lines.append(f"- {icon} {label}: {c} 条")
        lines.append(f"")
        lines.append(f"### 详细信息")
        lines.append(f"")
        for m in new_this_week:
            icon = TYPE_ICONS.get(m.get("type", ""), "📌")
            lines.append(f"- {icon} {m['content']}")
            if m.get("tags"):
                lines.append(f"  - 标签：{', '.join(m['tags'])}")
            lines.append(f"")
    if relations:
        lines.append(f"## 🔗 知识关联发现")
        lines.append(f"")
        lines.append(f"你的记忆之间形成了 {len(relations)} 组关联：")
        lines.append(f"")
        for r in relations[:5]:
            lines.append(f"- 「{r['content_a'][:30]}...」 ↔ 「{r['content_b'][:30]}...」")
        lines.append(f"")
    lines.append(f"## 💪 知识复利效应")
    lines.append(f"")
    lines.append(f"- 当前知识复利指数：**{stars}**（{kci}/100）")
    lines.append(f"- 累计为你节省了约 **{saved_hours}h** 的重复解释时间")
    lines.append(f"- 平均每条记忆被引用 **{total_access / max(total, 1):.1f}** 次")
    lines.append(f"- 知识库中有 **{len(relations)}** 组关联关系等待挖掘")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*知识复利引擎自动生成 · 数据仅存储在你本地*")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"📊 周报已生成：{report_path}")
    print(f"   你可以直接分享这个 Markdown 文件！")
    print(f"\n📈 本周摘要：")
    print(f"   记忆总数 {total} 条 | 本周新增 {len(new_this_week)} 条")
    print(f"   知识复利指数 {stars} | 节省 ≈ {saved_hours}h")


def cmd_relation(args):
    memories = _read_memories()
    if not memories:
        print("记忆库为空。")
        return
    relations = _discover_relations(memories)
    if not relations:
        print("未发现记忆之间的关联。继续使用，积累更多记忆后会自动发现关联。")
        return
    limit = args.limit or 10
    print(f"🔗 发现 {len(relations)} 组记忆关联：\n")
    for r in relations[:limit]:
        strength_bar = "█" * int(r["strength"] * 10) + "░" * (10 - int(r["strength"] * 10))
        print(f"  关联强度：{strength_bar} ({r['strength']:.0%})")
        print(f"  ├─ [{r['id_a']}] {r['content_a'][:50]}")
        print(f"  └─ [{r['id_b']}] {r['content_b'][:50]}")
        if r.get("common_words"):
            print(f"     共同关键词：{', '.join(r['common_words'][:5])}")
        print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知识复利引擎 - 记忆管理")
    sub = parser.add_subparsers(dest="command")

    p_store = sub.add_parser("store", help="保存一条记忆")
    p_store.add_argument("content", nargs="?", help="记忆内容")
    p_store.add_argument("--type", default="fact", choices=list(TYPE_LABELS.keys()), help="记忆类型")
    p_store.add_argument("--context", default="", help="产生记忆的上下文")
    p_store.add_argument("--tags", default="", help="逗号分隔的标签")

    p_recall = sub.add_parser("recall", help="检索相关记忆")
    p_recall.add_argument("content", nargs="?", help="检索关键词（不填则显示活跃记忆）")
    p_recall.add_argument("--limit", type=int, default=5, help="返回条数上限")

    p_list = sub.add_parser("list", help="列出最近记忆")
    p_list.add_argument("--limit", type=int, default=10, help="显示条数")

    p_search = sub.add_parser("search", help="搜索记忆")
    p_search.add_argument("content", nargs="?", help="搜索关键词")
    p_search.add_argument("--limit", type=int, default=10, help="返回条数上限")

    p_delete = sub.add_parser("delete", help="删除记忆")
    p_delete.add_argument("content", nargs="?", help="记忆 ID")

    sub.add_parser("export", help="导出所有记忆为 Markdown")
    sub.add_parser("cleanup", help="清理长期未访问的记忆")
    sub.add_parser("stats", help="记忆库统计")

    p_dash = sub.add_parser("dashboard", help="显示可视化仪表盘")
    p_weekly = sub.add_parser("weekly", help="生成周报")
    p_rel = sub.add_parser("relation", help="发现记忆之间的关联")
    p_rel.add_argument("--limit", type=int, default=10, help="显示条数")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    cmd_map = {
        "store": cmd_store,
        "recall": cmd_recall,
        "list": cmd_list,
        "search": cmd_search,
        "delete": cmd_delete,
        "export": cmd_export,
        "cleanup": cmd_cleanup,
        "stats": cmd_stats,
        "dashboard": cmd_dashboard,
        "weekly": cmd_weekly,
        "relation": cmd_relation,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
