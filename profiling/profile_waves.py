"""Profile each FEVS wave: rows, columns, weight, agency/demographic fields, response codes."""
import glob, json, re, sys
import duckdb

con = duckdb.connect()
out = {}
for path in sorted(glob.glob("data/extracted/*/*.csv")):
    year = path.split("/")[2]
    rel = con.sql(f"select * from read_csv('{path}', all_varchar=true, header=true, sample_size=-1)")
    cols = rel.columns
    n = con.sql(f"select count(*) from read_csv('{path}', all_varchar=true, header=true)").fetchall()[0][0]
    items = [c for c in cols if re.fullmatch(r"[QV]\d+[A-Z]?(_\d+)?", c, re.I)]
    other = [c for c in cols if c not in items]
    q = items[0] if items else None
    codes = con.sql(f"select \"{q}\" v, count(*) n from read_csv('{path}', all_varchar=true, header=true) group by 1 order by 1").fetchall() if q else []
    w = next((c for c in cols if c.upper() == "POSTWT"), None)
    wstats = con.sql(f"select min(try_cast(\"{w}\" as double)), max(try_cast(\"{w}\" as double)), sum(try_cast(\"{w}\" as double)) from read_csv('{path}', all_varchar=true, header=true)").fetchall()[0] if w else None
    out[year] = {"rows": n, "n_items": len(items), "first_item": items[:1], "last_item": items[-1:], "other_cols": other,
                 "codes_first_item": codes, "weight": w, "weight_min_max_sum": wstats}
    print(year, n, len(items), "weight" if w else "NO WEIGHT", other, file=sys.stderr)
json.dump(out, open("profiling/wave_profile.json", "w"), indent=1, default=str)
