#!/usr/bin/env python3
"""Fetch Trend Animal A-share signal lists and write docs/data.json.

API key is read from TRENDTRADER_API_KEY or the local API_KEY file.
It is only sent through the X-API-Key header and never printed or stored in output.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://www.trendtrader.cn/apiData/data"
TZ = ZoneInfo("Asia/Shanghai")
MAX_SNAPSHOT_IDS = 100
REQUEST_INTERVAL = 0.35


class ApiError(RuntimeError):
    pass


def load_api_key() -> str:
    key = os.environ.get("TRENDTRADER_API_KEY", "").strip()
    if key:
        return key
    key_file = ROOT / "API_KEY"
    if key_file.is_file():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise SystemExit(
        "缺少 API Key：请设置环境变量 TRENDTRADER_API_KEY，或在本目录放置 API_KEY 文件。"
    )


API_KEY = load_api_key()


def build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for path in (
        "/etc/ssl/cert.pem",
        "/usr/local/etc/openssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
    ):
        if os.path.isfile(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


SSL_CONTEXT = build_ssl_context()


def api_get(endpoint: str, params: dict | None = None, retries: int = 3):
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "X-API-Key": API_KEY,
            "Accept": "application/json",
            "User-Agent": "TrendAnimalDashboard/1.0",
        },
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=40, context=SSL_CONTEXT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429 or exc.code >= 500:
                wait = min(30, 2 ** attempt)
                print(f"  {endpoint} HTTP {exc.code}，{wait}s 后重试 ({attempt}/{retries})")
                time.sleep(wait)
                continue
            body = exc.read().decode("utf-8", "replace")[:300]
            raise ApiError(f"{endpoint} HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            wait = min(30, 2 ** attempt)
            print(f"  {endpoint} 网络错误，{wait}s 后重试 ({attempt}/{retries})")
            time.sleep(wait)
            continue

        if payload.get("code") != "00000":
            raise ApiError(
                f"{endpoint} 返回 code={payload.get('code')} msg={payload.get('msg')}"
            )
        return payload.get("data")
    raise ApiError(f"{endpoint} 重试 {retries} 次仍失败: {last_error}")


def ashare_status() -> dict:
    rows = api_get("getUpdateStatus") or []
    for row in rows:
        if row.get("asset") == "A股" or row.get("tickerName") == "A股":
            return row
    raise ApiError("getUpdateStatus 未返回 A股 数据状态")


def expected_latest_trading_date(now: datetime) -> date:
    day = now.date()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def wait_for_update(wait_minutes: int, now: datetime) -> dict:
    status = ashare_status()
    if wait_minutes <= 0:
        return status
    target = expected_latest_trading_date(now).isoformat()
    if status.get("asOfDate", "") >= target:
        return status
    if now.weekday() >= 5:
        return status

    deadline = time.monotonic() + wait_minutes * 60
    print(f"A股数据尚未更新到 {target}，每 120 秒查询一次免费状态，最多等待 {wait_minutes} 分钟…")
    while time.monotonic() < deadline:
        time.sleep(120)
        status = ashare_status()
        print(f"  当前 A股数据日期: {status.get('asOfDate')} / 更新: {status.get('updateDt')}")
        if status.get("asOfDate", "") >= target:
            return status
    print("等待超时，使用当前最新数据继续生成页面，并在页面标注数据日期。")
    return status


def fetch_column_costs() -> dict[str, dict]:
    rows = api_get("getSnapshotColumnBilling") or []
    return {row["columnName"]: row for row in rows}


def validate_fields(fields: list[str], columns: dict[str, dict]) -> None:
    unknown = [field for field in fields if field not in columns]
    if unknown:
        raise ApiError(f"字段不在实时计费表中，请核对: {', '.join(unknown)}")


def estimate_snapshot_cost(fields: list[str], columns: dict[str, dict], rows: int) -> float:
    unit = sum(float(columns[field].get("priceCost") or 0) for field in fields)
    full = min(rows, 20)
    discounted_80 = max(0, min(rows, 100) - 20) * 0.8
    discounted_60 = max(0, rows - 100) * 0.6
    return round(unit * (full + discounted_80 + discounted_60), 4)


def fetch_components(tm_id: int, label: str) -> list[dict]:
    rows = api_get(
        "getComponentTicker",
        {"tmId": tm_id, "getAllBasicComponentsFlag": 1},
    ) or []
    print(f"  {label}: {len(rows)} 个成分，数据日期 {rows[0].get('asOfDate') if rows else '—'}")
    time.sleep(REQUEST_INTERVAL)
    return rows


def fetch_snapshot(ids: list[int], fields: list[str]) -> list[dict]:
    rows: list[dict] = []
    for start in range(0, len(ids), MAX_SNAPSHOT_IDS):
        batch = ids[start : start + MAX_SNAPSHOT_IDS]
        data = api_get(
            "getTickerSnapshot",
            {"tmIds": ",".join(str(i) for i in batch), "fields": ",".join(fields)},
        ) or []
        print(f"  快照批次 {start // MAX_SNAPSHOT_IDS + 1}: 请求 {len(batch)}，返回 {len(data)}")
        rows.extend(data)
        time.sleep(REQUEST_INTERVAL)
    return rows


def clean(value):
    if value is None or value == "":
        return None
    return value


def build_member(snapshot: dict, component: dict) -> dict:
    prev_temp = clean(snapshot.get("trendTemperaturePrev"))
    curr_temp = clean(snapshot.get("trendTemperatureCurr"))
    change = None
    if prev_temp and curr_temp:
        change = f"{prev_temp}→{curr_temp}"
    roc = snapshot.get("roc")
    return {
        "tmId": snapshot.get("tmId") or component.get("tmId"),
        "name": snapshot.get("tickerName") or component.get("tickerName"),
        "symbol": clean(snapshot.get("tickerSymbol")) or clean(component.get("tickerSymbol")),
        "price": snapshot.get("priceIndex"),
        "dayChangePct": round(roc * 100, 2) if isinstance(roc, (int, float)) else None,
        "isRightSide": snapshot.get("isTrendRightSide"),
        "tempPrev": prev_temp,
        "tempCurr": curr_temp,
        "tempChange": change,
        "phase": clean(snapshot.get("trendPhaseCurr")),
        "strength": snapshot.get("trendStrengthLocalCurr"),
        "strengthChange": clean(snapshot.get("trendStrengthLocalChange")),
        "asOfDate": snapshot.get("asOfDate"),
    }


def sort_members(members: list[dict], key: str, reverse: bool) -> list[dict]:
    present = [m for m in members if isinstance(m.get(key), (int, float))]
    missing = [m for m in members if not isinstance(m.get(key), (int, float))]
    present.sort(key=lambda m: m[key], reverse=reverse)
    return present + missing


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取趋势动物 A股榜单并生成页面数据")
    parser.add_argument("--wait-minutes", type=int, default=20, help="等待当日数据更新的最长时间")
    parser.add_argument("--check", action="store_true", help="仅查询免费的数据更新状态后退出")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    args = parser.parse_args()

    now = datetime.now(TZ)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    status = wait_for_update(args.wait_minutes, now)
    print(
        f"A股数据日期: {status.get('asOfDate')} / 更新时间: {status.get('updateDt')} "
        f"/ 品种数: {status.get('tickerCount')}"
    )
    if args.check:
        return

    expected = expected_latest_trading_date(now).isoformat()
    as_of_date = status.get("asOfDate")
    stale = bool(as_of_date) and as_of_date < expected

    columns = fetch_column_costs()
    fields = config["fields"]
    validate_fields(fields, columns)

    lists_config = config["lists"]
    components: dict[str, list[dict]] = {}
    for key, item in lists_config.items():
        print(f"获取榜单 {item['name']} (tmId={item['tmId']})")
        components[key] = fetch_components(item["tmId"], item["name"])

    component_by_id: dict[int, dict] = {}
    for rows in components.values():
        for row in rows:
            component_by_id.setdefault(row["tmId"], row)

    ids = sorted(component_by_id)
    print(f"获取 {len(ids)} 个标的的趋势快照，字段: {', '.join(fields)}")
    snapshot_rows = fetch_snapshot(ids, fields)
    snapshot_by_id = {row["tmId"]: row for row in snapshot_rows}

    missing = [i for i in ids if i not in snapshot_by_id]
    if missing:
        print(f"警告: {len(missing)} 个标的未返回快照: {missing}")

    output_lists: dict[str, dict] = {}
    for key, item in lists_config.items():
        members = [
            build_member(snapshot_by_id[row["tmId"]], row)
            for row in components[key]
            if row["tmId"] in snapshot_by_id
        ]
        if key == "buy":
            members = sort_members(members, "strength", reverse=True)
            sorted_by = "trendStrengthLocalCurr 降序"
        else:
            members = sort_members(members, "dayChangePct", reverse=False)
            sorted_by = "当日涨跌幅升序（跌幅最大在前）"
        output_lists[key] = {
            "name": item["name"],
            "tmId": item["tmId"],
            "description": item.get("description"),
            "count": len(members),
            "sortedBy": sorted_by,
            "members": members,
        }

    snapshot_cost = estimate_snapshot_cost(fields, columns, len(snapshot_rows))
    component_cost = round(
        sum(0.1 + 0.005 * len(rows) for rows in components.values()), 4
    )

    snapshot_dates = {
        row.get("asOfDate") for row in snapshot_rows if row.get("asOfDate")
    }
    if len(snapshot_dates) > 1:
        print(f"警告: 快照包含多个数据日期: {sorted(snapshot_dates)}")

    output = {
        "schemaVersion": 1,
        "generatedAt": now.isoformat(timespec="seconds"),
        "source": {
            "name": "趋势动物 API",
            "url": "https://www.trendtrader.cn",
            "asset": config.get("asset", "A股"),
        },
        "asOfDate": as_of_date,
        "updateDt": status.get("updateDt"),
        "stale": stale,
        "expectedAsOfDate": expected,
        "lists": output_lists,
        "meta": {
            "fields": {
                field: {
                    "intro": columns[field].get("intro"),
                    "priceCost": columns[field].get("priceCost"),
                }
                for field in fields
            },
            "missingSnapshotIds": missing,
            "snapshotDates": sorted(snapshot_dates),
            "estimatedCost": {
                "currency": "CNY",
                "components": component_cost,
                "snapshot": snapshot_cost,
                "total": round(component_cost + snapshot_cost, 4),
                "note": "按公开计费规则估算，缓存命中与阶梯折扣使实际金额可能更低；以账户账单为准。",
            },
        },
    }

    output_path = ROOT / config.get("output", "docs/data.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp_path.replace(output_path)

    print(
        f"已写入 {output_path}：买入 {output_lists['buy']['count']} 个，"
        f"卖出 {output_lists['sell']['count']} 个，"
        f"估算费用 {output['meta']['estimatedCost']['total']} 元"
    )
    if stale:
        print(f"提示: 数据日期 {as_of_date} 早于预期交易日 {expected}，页面将标注。")


if __name__ == "__main__":
    try:
        main()
    except ApiError as exc:
        print(f"API 调用失败: {exc}", file=sys.stderr)
        sys.exit(1)
