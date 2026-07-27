"""Oracle CloudのAlways Free上限を、実際のリソース使用量から確認する監視スクリプト。

Pay As You Go(有償)アカウントはAlways Freeの上限を超えても自動では止まらず、
超えた分がそのまま課金される。このスクリプトは`oci`CLIで実際の使用量を集計し、
上限に対してどれだけ余裕があるかを表示するだけで、リソースの削除・停止は
一切行わない(誤って本物のインスタンス/ボリュームを消してしまう事故を避けるため、
判断と実際の削除操作は必ず那由多さん自身が行う)。

使い方:
    export OCI_COMPARTMENT_ID=ocid1.tenancy.oc1..xxxx
    python scripts/oracle_usage_guard.py

前提: `oci`CLIがインストール・認証済みであること(retry_launch.shと同じ環境)。

このリポジトリはGitHub上でPublicなため、テナンシーOCID自体は秘密情報では
ないものの、アカウントを特定できる情報を不必要にソースへ埋め込まないよう、
環境変数からのみ読み込む(ハードコードしない)。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

COMPARTMENT_ID = os.environ.get("OCI_COMPARTMENT_ID")
if not COMPARTMENT_ID:
    print("環境変数OCI_COMPARTMENT_IDが設定されていません。", file=sys.stderr)
    sys.exit(1)

# Always Freeの上限(2026年6月時点、docs/deploy_oracle.md参照)
LIMIT_A1_OCPU = 4
LIMIT_A1_MEMORY_GB = 24
LIMIT_E2_MICRO_COUNT = 2
LIMIT_BLOCK_STORAGE_GB = 200

# 警告を出す閾値(上限そのものではなく、余裕を持って早めに気づけるようにする)
WARNING_RATIO = 0.8


def _run_oci(args: list[str]) -> dict:
    result = subprocess.run(["oci", *args, "--output", "json"], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"oci CLI実行に失敗しました: {' '.join(args)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    if not result.stdout.strip():
        # このoci CLIには、結果が空リストの時にreturncode=0のままstdoutに
        # 何も出力しないクセがある(--debugで見るとAPI自体は200 "data": []を
        # 返している)。空文字列を「空リスト」として扱う。
        return {"data": []}
    return json.loads(result.stdout)


def _report_line(label: str, used: float, limit: float, unit: str) -> bool:
    """1行分の使用量を表示し、警告閾値を超えていればTrueを返す。"""
    ratio = used / limit if limit else 0
    if used > limit:
        status = "🔴 上限超過"
    elif ratio >= WARNING_RATIO:
        status = "🟡 警告(閾値超え)"
    else:
        status = "🟢 余裕あり"
    print(f"{label}: {used:.1f}/{limit:.1f} {unit} ({ratio * 100:.0f}%) {status}")
    return used > limit


def main() -> None:
    print("Oracle Cloud Always Free 使用量チェック")
    print("(このスクリプトはリソースの削除・停止を一切行いません。警告表示のみです)")
    print()

    instances = _run_oci(
        ["compute", "instance", "list", "--compartment-id", COMPARTMENT_ID, "--lifecycle-state", "RUNNING"]
    )["data"]

    a1_ocpu_total = 0.0
    a1_memory_total = 0.0
    e2_micro_count = 0

    for instance in instances:
        shape = instance.get("shape", "")
        if shape == "VM.Standard.A1.Flex":
            shape_config = instance.get("shape-config") or {}
            a1_ocpu_total += shape_config.get("ocpus", 0)
            a1_memory_total += shape_config.get("memory-in-gbs", 0)
        elif shape == "VM.Standard.E2.1.Micro":
            e2_micro_count += 1

    volumes = _run_oci(["bv", "volume", "list", "--compartment-id", COMPARTMENT_ID])["data"]
    boot_volumes = _run_oci(["bv", "boot-volume", "list", "--compartment-id", COMPARTMENT_ID, "--all"])["data"]
    total_storage_gb = sum(v.get("size-in-gbs", 0) for v in volumes) + sum(
        v.get("size-in-gbs", 0) for v in boot_volumes
    )

    over_limit = False
    over_limit |= _report_line("A1.Flex OCPU合計", a1_ocpu_total, LIMIT_A1_OCPU, "OCPU")
    over_limit |= _report_line("A1.Flex メモリ合計", a1_memory_total, LIMIT_A1_MEMORY_GB, "GB")
    over_limit |= _report_line("E2.1.Micro インスタンス数", e2_micro_count, LIMIT_E2_MICRO_COUNT, "台")
    over_limit |= _report_line("ブロック/ブートストレージ合計", total_storage_gb, LIMIT_BLOCK_STORAGE_GB, "GB")

    print()
    if over_limit:
        print("⚠️ Always Freeの上限を超えている項目があります。課金が発生している可能性があります。")
        print("   実際に削除・停止するかどうかは、Oracle Cloudコンソールで内容を確認した上で")
        print("   ご自身の判断で行ってください(このスクリプトは自動では何もしません)。")
    else:
        print("✅ 現時点ではAlways Freeの上限内に収まっています。")

    print()
    print("注: 月間10TBの送信データ転送量はこのスクリプトでは計測していません")
    print("   (時系列の累積値であり、一時点のスナップショットでは確認できないため)。")


if __name__ == "__main__":
    main()
