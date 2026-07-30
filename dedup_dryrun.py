#!/usr/bin/env python3
"""Non-destructive dry-run dedup analysis for v4_clause_item.

READ-ONLY. Opens the DB with mode=ro and issues SELECT-only queries. It never
writes, mutates, or backs up the database. It only produces JSON/text reports in
scratchpad/ for a human to review before any (separate) DB mutation.

Classification within each (file_key, verbatim) duplicate-verbatim group:
  * EXACT_DUP  (safe-collapse): items that ALSO share an identical semantic tuple
      (proposition, statement_polarity, subject_role, counterparty_role, action,
       object_type, effective_time, taxonomy_id). Collapse rule = keep the lowest
       item_id, the rest are removable.
  * DISTINCT_PROP (keep): same verbatim but a differing tuple -> a single sentence
       legitimately carrying multiple distinct propositions. Keep all.
"""

import json
import os
import random
import re
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join("cs_index", "catalog.sqlite")
OUT_JSON = os.path.join("scratchpad", "dedup_dryrun.json")
OUT_SAMPLES = os.path.join("scratchpad", "dedup_samples.txt")

# Density threshold matches audit_t3_v4.OVERSEGMENTATION_DENSITY_THRESHOLD.
DENSITY_THRESHOLD = 5

# The semantic tuple whose equality defines a genuine redundant copy.
TUPLE_FIELDS = (
    "proposition",
    "statement_polarity",
    "subject_role",
    "counterparty_role",
    "action",
    "object_type",
    "effective_time",
    "taxonomy_id",
)


def prefix_bucket(item_ref):
    """Bucket an item_ref into RWRX / RW / REM / COV / other."""
    m = re.match(r"^([A-Za-z]+)", item_ref or "")
    p = m.group(1) if m else ""
    if p in ("RWRX", "RW", "REM", "COV"):
        return p
    return "other"


def connect_ro(path):
    uri = "file:{}?mode=ro".format(path.replace(os.sep, "/"))
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def main():
    random.seed(20260729)
    os.makedirs("scratchpad", exist_ok=True)
    con = connect_ro(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM v4_clause_item")
    total_items = cur.fetchone()[0]

    # ------------------------------------------------------------------
    # Load every item that lives in a duplicate-verbatim group.
    # A duplicate-verbatim group = (file_key, verbatim) with >1 item and
    # non-empty verbatim.
    # ------------------------------------------------------------------
    cols = ["item_id", "file_key", "verbatim", "family", "item_ref"] + list(TUPLE_FIELDS)
    cur.execute(
        """
        SELECT {cols}
        FROM v4_clause_item
        WHERE TRIM(verbatim) <> ''
          AND (file_key, verbatim) IN (
              SELECT file_key, verbatim
              FROM v4_clause_item
              WHERE TRIM(verbatim) <> ''
              GROUP BY file_key, verbatim
              HAVING COUNT(*) > 1
          )
        ORDER BY file_key, verbatim, item_id
        """.format(cols=", ".join(cols))
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Group rows by (file_key, verbatim).
    groups = defaultdict(list)
    for r in rows:
        groups[(r["file_key"], r["verbatim"])].append(r)

    dup_group_count = len(groups)

    # ------------------------------------------------------------------
    # Classify. Within each group, cluster by the semantic tuple.
    # ------------------------------------------------------------------
    def tuple_of(r):
        return tuple(r[f] for f in TUPLE_FIELDS)

    removable_total = 0
    kept_repr_total = 0  # the surviving representative of each exact-dup cluster
    distinct_total = 0

    removable_by_family = defaultdict(int)
    removable_by_prefix = defaultdict(int)
    distinct_by_family = defaultdict(int)
    distinct_by_prefix = defaultdict(int)

    exact_cluster_samples = []   # (file_key, verbatim, tuple, [item_ids])
    distinct_group_samples = []  # (file_key, verbatim, [(item_id, item_ref, tuple)])

    largest_exact = []  # (n_copies, file_key, verbatim, item_ids)

    for (file_key, verbatim), items in groups.items():
        clusters = defaultdict(list)
        for r in items:
            clusters[tuple_of(r)].append(r)

        group_has_distinct = len(clusters) > 1

        for tup, members in clusters.items():
            members_sorted = sorted(members, key=lambda r: r["item_id"])
            if len(members_sorted) > 1:
                # exact-dup cluster: keep lowest item_id, rest removable
                keep = members_sorted[0]
                removable = members_sorted[1:]
                kept_repr_total += 1
                removable_total += len(removable)
                for r in removable:
                    removable_by_family[r["family"]] += 1
                    removable_by_prefix[prefix_bucket(r["item_ref"])] += 1
                exact_cluster_samples.append(
                    (file_key, verbatim, tup, [r["item_id"] for r in members_sorted])
                )
                largest_exact.append(
                    (len(members_sorted), file_key, verbatim, [r["item_id"] for r in members_sorted])
                )
            else:
                # singleton tuple inside a dup-verbatim group -> DISTINCT_PROP keep
                r = members_sorted[0]
                distinct_total += 1
                distinct_by_family[r["family"]] += 1
                distinct_by_prefix[prefix_bucket(r["item_ref"])] += 1

        if group_has_distinct:
            distinct_group_samples.append(
                (
                    file_key,
                    verbatim,
                    [(r["item_id"], r["item_ref"], tuple_of(r)) for r in sorted(items, key=lambda x: x["item_id"])],
                )
            )

    # top 10 largest exact-dup clusters
    largest_exact.sort(key=lambda t: t[0], reverse=True)
    top10 = [
        {
            "file_key": fk,
            "verbatim": vb[:120],
            "n_copies": n,
            "item_ids": ids,
        }
        for (n, fk, vb, ids) in largest_exact[:10]
    ]

    # ------------------------------------------------------------------
    # (5) paragraph_oversegmented density: count only, do not propose collapse.
    # Mirror audit logic: (family, file_key, loc_start) with >= DENSITY_THRESHOLD
    # items. Report both the number of dense buckets and the items in them.
    # ------------------------------------------------------------------
    cur.execute(
        """
        WITH dense AS (
          SELECT file_key, family, loc_start, COUNT(*) AS n
          FROM v4_clause_item
          GROUP BY file_key, family, loc_start
          HAVING n >= ?
        )
        SELECT COUNT(*) AS bucket_count, COALESCE(SUM(n), 0) AS item_count
        FROM dense
        """,
        (DENSITY_THRESHOLD,),
    )
    d = cur.fetchone()
    paragraph_overseg = {
        "density_threshold": DENSITY_THRESHOLD,
        "dense_bucket_count": d["bucket_count"],
        "flagged_item_count": d["item_count"],
        "note": "count only; NOT proposed for collapse (needs proposition-level judgment)",
    }

    # ------------------------------------------------------------------
    # Assemble report.
    # ------------------------------------------------------------------
    report = {
        "db": DB_PATH,
        "read_only": True,
        "total_items": total_items,
        "duplicate_verbatim_groups": dup_group_count,
        "items_in_duplicate_verbatim_groups": len(rows),
        "exact_dup": {
            "removable_item_count": removable_total,
            "kept_representative_count": kept_repr_total,
            "removable_by_family": dict(sorted(removable_by_family.items())),
            "removable_by_item_ref_prefix": dict(sorted(removable_by_prefix.items())),
        },
        "distinct_prop": {
            "keep_item_count": distinct_total,
            "keep_by_family": dict(sorted(distinct_by_family.items())),
            "keep_by_item_ref_prefix": dict(sorted(distinct_by_prefix.items())),
        },
        "top10_largest_exact_dup_groups": top10,
        "paragraph_oversegmented": paragraph_overseg,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # (4) Random samples for human verification.
    # ------------------------------------------------------------------
    ex_sample = random.sample(exact_cluster_samples, min(15, len(exact_cluster_samples)))
    dp_sample = random.sample(distinct_group_samples, min(15, len(distinct_group_samples)))

    lines = []
    lines.append("=" * 100)
    lines.append("EXACT_DUP SAMPLES (safe-collapse: keep lowest item_id, drop the rest)")
    lines.append("=" * 100)
    for i, (fk, vb, tup, ids) in enumerate(ex_sample, 1):
        lines.append("\n--- EXACT_DUP sample #{} ---".format(i))
        lines.append("file_key : {}".format(fk))
        lines.append("item_ids : {}  (keep {}, remove {})".format(ids, ids[0], ids[1:]))
        lines.append("shared tuple:")
        for fld, val in zip(TUPLE_FIELDS, tup):
            lines.append("    {:18} = {!r}".format(fld, val))
        lines.append("verbatim :")
        lines.append("    " + (vb or "").replace("\n", "\n    "))

    lines.append("\n\n" + "=" * 100)
    lines.append("DISTINCT_PROP SAMPLES (keep all: same verbatim, differing semantic tuple)")
    lines.append("=" * 100)
    for i, (fk, vb, members) in enumerate(dp_sample, 1):
        lines.append("\n--- DISTINCT_PROP sample #{} ---".format(i))
        lines.append("file_key : {}".format(fk))
        lines.append("verbatim :")
        lines.append("    " + (vb or "").replace("\n", "\n    "))
        lines.append("members ({}):".format(len(members)))
        for item_id, item_ref, tup in members:
            lines.append("  - item_id={} item_ref={}".format(item_id, item_ref))
            for fld, val in zip(TUPLE_FIELDS, tup):
                lines.append("      {:18} = {!r}".format(fld, val))

    with open(OUT_SAMPLES, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ------------------------------------------------------------------
    # Console summary.
    # ------------------------------------------------------------------
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nSamples written to:", OUT_SAMPLES)
    print("JSON written to    :", OUT_JSON)
    con.close()


if __name__ == "__main__":
    main()
