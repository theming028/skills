#!/usr/bin/env python3
"""
知识复利引擎 - 记忆存储和检索脚本

使用方式（被 SOLO 调用，用户无需直接操作）：
  python3 memory_bank.py store <内容> --type <类型> --context <上下文> --tags <标签>
  python3 memory_bank.py recall <关键词>
  python3 memory_bank.py list [--limit N]
  python3 memory_bank.py search <关键词>
  python3 memory_bank.py delete <记忆ID>
  python3 memory_bank.py export
  python3 memory_bank.py cleanup
"""

import json
from datetime import datetime, date
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / ".knowledge-compound"
MEMORY_FILE = MEMORY_DIR / "memory-bank.json"


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
    print(f"记忆已保存：{mem['id']} ({mem['type']})")


def cmd_recall(args):
    query = args.content or ""
    if not query.strip():
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
        print(f"  [{m['id']}] ({m['type']}) {m['content']}")
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
        tags_str = ", ".join(m.get("tags", [])) if m.get("tags") else ""
        tag_info = f" [{tags_str}]" if tags_str else ""
        print(f"  [{m['id']}] ({m['type']}) {m['content']}{tag_info}")
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
        lines.append(f"## [{m['id']}] ({m['type']})")
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
    type_counts = {}
    for m in memories:
        t = m.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    total = len(memories)
    avg_access = sum(m.get("access_count", 0) for m in memories) / total
    print(f"📊 记忆库统计")
    print(f"  {'='*30}")
    print(f"  总记忆数：{total}")
    print(f"  按类型：")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c} 条")
    print(f"  平均引用次数：{avg_access:.1f}")
    print(f"  存储位置：{MEMORY_FILE}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知识复利引擎 - 记忆管理")
    sub = parser.add_subparsers(dest="command")

    p_store = sub.add_parser("store", help="保存一条记忆")
    p_store.add_argument("content", nargs="?", help="记忆内容")
    p_store.add_argument("--type", default="fact", help="记忆类型：preference/decision/fact/project/lesson")
    p_store.add_argument("--context", default="", help="产生记忆的上下文")
    p_store.add_argument("--tags", default="", help="逗号分隔的标签")

    p_recall = sub.add_parser("recall", help="检索相关记忆")
    p_recall.add_argument("content", nargs="?", help="检索关键词")
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
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
