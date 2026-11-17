"""Order-v2 study: final_answer before versus after the derivation array.

This is a new, additive harness.  It does not modify the frozen ceiling,
held-out, memory or Round 3/4 modules.  It writes only new ``block15_order_v2_*``
stores and result files.  No generation happens at import or in ``--manifest``
mode; generation only happens in ``--run``.

Design (pre-registered in PREREG_ORDER_V2.md):

* 30 fresh bounded-math tasks, independent of Round 3, H1-H5 and C01-M08:
  15 coefficient-extraction and 15 bounded-minimality tasks.
* Two arms share the contract-v2 neutral instruction plus exactly one added
  sentence; only the schema's required/property order differs:
  ``ANSWER_FIRST_V2`` versus ``DERIVATION_FIRST_V2``.
* One call per task per arm, both arms sequential in one process, arm order
  ``answer_first`` then ``derivation_first``.  No retry, repair, memory
  injection, teacher hint, or sampling change.
* Primary endpoint: numerically correct ``final_answer`` under an independent
  SymPy audit, non-copy.  Confidence-range violations never disqualify it.
* Hard cumulative call, runtime and free-memory guards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import sympy

from block15.contract_v2 import (
    ANSWER_FIRST_V2,
    DERIVATION_FIRST_V2,
    OUTPUT_INSTRUCTION_V2,
    SYSTEM_PROMPT_V2,
    emission_order_provenance,
    emitted_key_order,
    validate_v2,
)
from block15.round3 import _number_present
from block15.run_benchmark import DATA_DIR, _now, free_physical_mb
from mdl.config import Settings, load_settings
from mdl.errors import ModelError, ModelOutputError, ModelTimeoutError
from mdl.logging_store import ResearchStore
from mdl.ollama_client import OllamaClient

MODEL = "lfm3base:latest"
MODEL_DIGEST = "b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d"
QUANTIZATION = "Q4_K_M"

NUM_CTX = 8192
NUM_PREDICT = 1200
TEMPERATURE = 0.1
TOP_P = 1.0
REPEAT_PENALTY = 1.1
SEED = 42
KEEP_ALIVE = "10m"
THINK = False

MAX_CALLS = 70
MAX_RUNTIME_S = 5400.0
MIN_FREE_MB = 450.0
PLANNED_CALLS = 60

STORE_DB_NAME = "block15_order_v2.sqlite3"
STORE_JSONL_NAME = "block15_order_v2_events.jsonl"
RESULTS_PREFIX = "block15_order_v2_results_"
SUMMARY_NAME = "block15_order_v2_summary.json"

# The ONE sentence added on top of the shared neutral contract-v2 instruction.
SCHEMA_ORDER_SENTENCE = (
    "Emit the fields in the order required by the schema, not in the order "
    "they are listed here."
)
EFFECTIVE_INSTRUCTION_V2 = (
    OUTPUT_INSTRUCTION_V2 + "\n\n" + SCHEMA_ORDER_SENTENCE
)

ARMS: tuple[str, ...] = ("answer_first", "derivation_first")
SCHEMAS: dict[str, dict] = {
    "answer_first": ANSWER_FIRST_V2,
    "derivation_first": DERIVATION_FIRST_V2,
}


# Frozen baselines captured at the pre-registration commit.  Generated from
# on-disk hashes (FROZEN) and git blobs at 6c788a5 (LIVE before).  Do not edit
# by hand; see PREREG_ORDER_V2.md.
# --- BEGIN EMBEDDED BASELINE ---
FROZEN_BASELINE_SHA256 = {
    ".python-version": "db3ef967a80f30770e652243d4e8292c73ee214e182ada70ce045e91aab40fa7",
    "BLOCK15_REPORT.md": "1810bcf7d8e710bc202de0533bba86e8274481863671582b001a3de95ed23b3a",
    "BLOCK15_ROUND2_REPORT.md": "3ac30888b06e20b60b0b3379de677be5afaa12a01e565e7835af4774c6b5843a",
    "BLOCK15_ROUND3_REPORT.md": "283eb0c07163fcf0889b8435480e9b3abb0cdf4d392df78daf127f01c4cdd382",
    "PREREG_CEILING_BUDGET.md": "4b3925fb9b0ae316ba29c7461e7c6343183d4e65823e1c4c7d3bc198f9e827d3",
    "PREREG_CEILING_SCHEMA.md": "759d7c3007b564a2b946e41afe1e69fcf70aecbc4248a144a753d344de15c131",
    "PREREG_HELDOUT_BASELINE.md": "2838a90ddc3b39ebaa123e1bddadc56ce0a618f71e1e3f4a56f38c5912ccaa20",
    "PREREG_HELDOUT_NUMPREDICT.md": "ca3eb4cc4fc9ed676155f06ebee6fbf285c329182730ccf39aea9c3626d2b492",
    "PREREG_HELDOUT_SCHEMA.md": "f0791a23a840049b58eec901882faa1fca60bcdd957e121db8f2d66ac31e7291",
    "PREREG_HELDOUT_TEMPERATURE.md": "c030a675c1a3e25250360e93fcf722d17ac643de87647232c7e3df228887fa3f",
    "PREREG_MEMORY.md": "38cb30731a55aaf3ad89e26c35cc2e267086c2751c5d4c906e4f0a2e823904fe",
    "PREREG_QAD.md": "87a3dd0a24fe7c6ff7431521a84ccd95b7955995a32bed805a6b3124f5a1058f",
    "README_BLOCK1.md": "4ea8aac202e9a5ef2d2864d9abec0eaba3bd46c73e948e11445c9cf86e851991",
    "README_BLOCK2A.md": "a7a0c2ddc24922708fac1bd0b5993b25bd88bdd502e24a5fc5ffa5c54ea2f8a1",
    "README_BLOCK2B.md": "70bd8c88ba4cf8723c85060165f9b2e22606bdea0c38b5ad7e0b31d1c0ffb28d",
    "REPORT_CEILING.md": "f06ab903da2d4ad82bd4ad44219778d0fa9946909df5047dec3d729681cf05e1",
    "REPORT_MEMORY.md": "6719d36a832bd56d023d690ab2b76a132aeccc62c6452c726e2a6aad089cf766",
    "REPORT_QAD.md": "6f1814f7cb53ace8e1e0d76ce9b95584277f7a161f8a610f75871a843772394c",
    "REPORT_RESEARCH.md": "1fac5ba6ba53424c9e9e614b181b75c0643567eba2467793777ab69e06412026",
    "block15/ceiling_research.py": "65334ef0d302bea063a062d7f585a20b942a1dc4f401da5509c121fcfc5da513",
    "block15/heldout_research.py": "396e44b1e5446d2600da5d7f2ea0258a5024c3a9ff403b3612f649959ea07488",
    "block15/memory_pilot.py": "f928281cbc198be2c6aec9be6716363f9eae9bcc3e598ab1aa4cbd242f8e34c0",
    "block15/round2.py": "d6c3b43dc6d080e2442bf6d9dda7a886a7c0573e732e4e1d0f89a00f58b8cc9f",
    "block15/round2_recover.py": "c70ad539a32f3bc053a59f5aa58ff7419e2f3b7959438c01f419a8412509723d",
    "block15/round2_report.py": "1f948560d07197878752037640d9b9a7c1d774cde928159a26ffa57e198331a8",
    "block15/round2_tasks.py": "7917d3b5d9a0c3ea29f7511534e180876db61fc3f722b60b7b7d48e9577ae796",
    "block15/round3.py": "99c80b92bbc81af2da2c0b8fe59e1c79206455d300398af71ea1e7a11c29e99a",
    "block15/round3_preflight.py": "71441211930c25a969759ad6449c846aab5e4daaa382b168c001369745100289",
    "block15/round3_report.py": "8a4ee7ae77ef547ade61eb71edeb2b0f3b9330309a7c7cbc83eefb781835f663",
    "block15/round3_tasks.py": "ed2a9354c1ef11b18d25441ab57a1b7429212bc746adc51afc9534a69e0e84f2",
    "block15/round4_scoring.py": "7489b2fa65aef2b95483b099ccfb12bbd427d645fd4bf35077701cce3b1d2843",
    "block15/run_benchmark.py": "cd763efe7ca598ba893a7a6db08b53f5371ad4675147b29e93f183aa5268cc4c",
    "block15/tasks.py": "742c2970d4fca6297d9f66d9fd931fb53e55ac8fb72ffb78ef6ddb58d8fc59c6",
    "data/REPORT_CEILING.template.md": "9e6e11d499ff7d3439afbdde61c88b3f6cb7d4fbd8fafa6c6ecb4cd33d7fd436",
    "data/block15.sqlite3": "19abbf88fd6e0a927fa93b4cae398b2871d43bbc95014809b85c50c41ef1fef8",
    "data/block15_assessments_20261110T204340Z.json": "a0258f9430e832ce5d633153a61db324d7a3b5908d1b4d198ff9fd7c68bfeb50",
    "data/block15_ceiling.sqlite3": "6ebd5e02fb933cf52d507bc3c61033c24c4fe31b027d70581d59f91e47821f6b",
    "data/block15_ceiling_events.jsonl": "494b8e8fd64cdb9dbc988bfddc68b2fdea68c1c21db5a2253940015598f64902",
    "data/block15_ceiling_results_answer_first_1200_20261115T194214Z.json": "1ba97edb559a96661cb806d8c53de590c100e41ac598a4c7b23cdc72f1f17cae",
    "data/block15_ceiling_results_derivation_first_1200_20261115T201101Z.json": "b2f7b0f39380b60a6a131591063abcd2e7b05c8aa21fe437120fe55882b9a018",
    "data/block15_ceiling_results_derivation_first_2400_20261116T110703Z.json": "aefac9b1350cc35e89ee11fa702b79497610ddeff2d7f9e6c74255068dbf57be",
    "data/block15_ceiling_summary_final.json": "c2fcbf0cc2892db551dede9252091eeca6088af45311b8df8e5bbdce939bb77e",
    "data/block15_diagnostics_diag_20261110T205129Z.json": "bcd308ba9219d68c4d5fe4636befb1ff0e6ff2e5911f2c06c2bf7e62d242f746",
    "data/block15_events.jsonl": "ea38fac420a26e005125b23593901dfcfa16901c5107ea27c654470b94ee8019",
    "data/block15_heldout.sqlite3": "e6516b01816d362bb0defa012170371dca71e9206ab96246b28a2bcc1520be87",
    "data/block15_heldout_events.jsonl": "5eba5fcf5b3dad61bd1ac733a9fddde882efd3e6e4e21515350e99e39f01a28b",
    "data/block15_heldout_results_baseline_20261115T185523Z.json": "cea477ebb8b1e3228fa6325f657822afe031649739aa8e22b21886c0f9bf8fcf",
    "data/block15_heldout_results_numpredict_20261115T190551Z.json": "3bc516bccb2062d43fc54d45a22f49e32bd37cde36acb0607e017a34084ea21e",
    "data/block15_heldout_results_schema_20261115T190224Z.json": "92a6bc19c1fb3897d8378b422cbd3c257a8ace9b5c745e59a5c1cf7cd068d90b",
    "data/block15_heldout_results_temperature_20261115T191207Z.json": "05ffcb2088452525cb0fef9a9cf6486117f4bf2c11a340cd84e0767809ce74e4",
    "data/block15_pilot_memory.sqlite3": "8d49d2746d08ff3d7c4a5f2c797a8e3cff74e3764971f6d9da81233631c7a02f",
    "data/block15_pilot_memory_events.jsonl": "57a59d883a3c9e096439407e19585a3478285b12b65a4f0bb08e9bf2b4105b21",
    "data/block15_pilot_memory_results_20261115T174655Z.json": "8de84c44f7dbf38d85e762354084600bb8d87248002bfcfd2dc00da4a98b52f6",
    "data/block15_results_20261110T202848Z.json": "acc7113ba95a0231df8d872900d5df902bf48acc267d434a9e60caa33185100a",
    "data/block15_results_20261110T203527Z.json": "3b9ad8eab9434e754c657805670bfc63bf61176ce601b91eddfef4a5eeef67d1",
    "data/block15_results_20261110T204249Z.json": "fd87f58be78380e2e3bef5e13a029fb64a4315c91217c72b4ae0ee677b0f3b01",
    "data/block15_results_20261110T204340Z.json": "b0ef076f7bb68f62a5f8cc2170365867e0429ee63bf77c9ea5bbfca61c183929",
    "data/block15_round2.sqlite3": "1f10a2c1981d1109e3e9ab809c59f0e5c0d1be5fffec0d0e1abafb0d5c47dbb4",
    "data/block15_round2_assessments.json": "2a0b06625a2c893a4faac7fe6e7fa91c465904e36061c925b0ea561cf42eb18c",
    "data/block15_round2_events.jsonl": "fd585556cbf973e4310b56b430ec65e4e16239e0338757f12a8e11eb63bed2bf",
    "data/block15_round2_recovery_round2_recovery_20261110T215749Z.json": "18e2a877a4b157e894e89cb131c51a3bd989faf03b9e919af3199f0f3d1b1120",
    "data/block15_round2_results_round2_20261110T214854Z.json": "980761fdc7cecd05e5548af31f91d3c65baf8f2f57eb9f64b987012f23a29365",
    "data/block15_round3.sqlite3": "ec1bfab2e10156e4d9148ece4703153dd5d8ca7f6a12c1c71a76e093343af542",
    "data/block15_round3_assessments.json": "75d711633f94743420be1f7bdc071e34843e18b89623688c6abd7e2ac6be4511",
    "data/block15_round3_events.jsonl": "d923e8c0a45674a98dc16f5ad47aa4f372f69d633c4d2faf4b674e5374d7136e",
    "data/block15_round3_ground_truth.json": "4239f09c454d5d7acfc544600f5b28c073d03a69e512ffcf663837ea0c7f45cd",
    "data/block15_round3_results_round3_20261111T143825Z.json": "8ebb5899304602be17c945cb7769378cff8fa5a7776956ec332f0730df7cf87e",
    "data/block15_round4_arm_a.sqlite3": "7563eae8cd692f5779614389c07a5cd040b0bb970dc1b1e378c54793a90afb16",
    "data/block15_round4_arm_a_events.jsonl": "68877cdae62296bb6667e5600ef169580633ad248e3c4684860adfe40ff57fe5",
    "data/block15_round4_arm_a_results_round3_20261114T215552Z.json": "d6f39e7dde69561c9ab00a0404c815a3d03ded94c9b86c581c793dfd3aa734d8",
    "data/block15_round4_arm_b.sqlite3": "d985e8ffd6d684dca15e70ab3d93f2734f77744a1b619c6cc9bc272a6a4cf82a",
    "data/block15_round4_arm_b_events.jsonl": "710fc7f02df6f6fcafebe6938559b766bda31f034b4c30bd8e68b9375287d9a4",
    "data/block15_round4_arm_b_results_round3_20261114T220133Z.json": "6d24f3b2e412ae0e2b805c9888da3518bb219e6c5a00ea84ee1acfe2e1950f6d",
    "data/ceiling_audit_unit.py": "da5633386b7633258ba5d947321512d1cc776348d9b03ea87e82593ea8a457e6",
    "data/ceiling_candidates.py": "649c3c7a49672a5e52839c1bbe9b77d18b15900ac9d3c98edef7378bbbd42ab9",
    "data/ceiling_coeff_check.py": "48aa5474c3d5958db36094c56f8dbca032a03990ff20f53807f977869e71dc5f",
    "data/ceiling_independent_audit.json": "49fa47202eecd554a8fea6855be3c95fee446154329abe1a972189c610976cde",
    "data/ceiling_independent_audit.py": "7c2c527d7d38e57a82f66cd6178b1446ee959bb0fa4c0deadc5371473ce9fa71",
    "data/ceiling_independent_audit_stdout.json": "bad0623fe0398cfcae1faebce1851ba1b779ab185d7a413b19e2ca78f5fa97bf",
    "data/ceiling_inspect.py": "0cab132c9f17e01bb02231f064b32ae3660d1fc28998c56ee6c642eb910ea1fa",
    "data/ceiling_inspect.txt": "dba83c762409616516648673eab646f81bf5b92949f3d23cb7904f5f49f0dd39",
    "data/ceiling_make_report.py": "b4350301cfadcb6ad7c2f4ddde95990b4f4cfa573c23287cabfb109217feda37",
    "data/ceiling_manifest.json": "413775e561f209e3bc2731a088f8a92e641a45772923a42ef4aeb3b1e49c25e5",
    "data/ceiling_passes.py": "fb68d75f3d2c3ecbaf881acc23d358c399002a9a22d3779ea29c829ae17be570",
    "data/ceiling_peek.py": "002265ec354097d94dacbc1ca9f02d61236667f3fd670769d2bbfb51b1270cb7",
    "data/ceiling_recheck_final.json": "afbea369e04537d2e83218d5e511ff7e90c85d65ef6ffd17ce159652008f3d26",
    "data/ceiling_report_check.py": "f0bf7f0f870c851cd4926e18a97d67c4f6be2da31b8fce1b7921041735972514",
    "data/ceiling_report_tables.md": "01f52dba60a30813922fc3e74b4566a408e3ea023ce283d93b3f09ddba42546b",
    "data/ceiling_report_tables.py": "2a920eba1b92ef989efe43b166fa7a35eefb405ae1c305991938dc6e095f946f",
    "data/ceiling_selfcheck.json": "de842952449fcd28171de308347c225193e85415a045cc13492030322f73f892",
    "data/ceiling_summary_after_exp1.json": "a908c46ffd2e68add74effe8a8c80db803917e59799d5e979234ec8e42c92f20",
    "data/ceiling_summary_dryrun.json": "a3ab88f0f6f07b94a812596265217dd0c389a6bf0ac46cc6495bae18c127579f",
    "data/ceiling_summary_final_stdout.json": "042e1a04e3df504977525ab819669b1d58ecf579ec3ffaf6bf45d43b0f5781ab",
    "data/ceiling_table.py": "9db5e3eb70b432c70e5dfa12f88a85b4df8f5008d546cfd868ce9df4252625a2",
    "data/ceiling_table_final.md": "d52e195efc4217c40d1fd3d75ac2950758d3077225ae02d6b26f9df79db06ba9",
    "data/ceiling_tables2.md": "add29884c6bd71027335f5d8f393b61008ae770e837fb8de5839655c5f063df0",
    "data/ceiling_tables2.py": "19a5c991a3e0b24a52089bad0d942563a33e50048010d1ccc4bff9e72817f85e",
    "data/ceiling_verify_tasks.py": "2ae7d917b52a9f129ca46542913f5642891d1aa0e50e469dd80a6873f7d9f5b7",
    "data/mdl.sqlite3": "2202e15f2f833efc231a901bd95b951be1d3bfac4ccd6fa728e7910655b0cec2",
    "data/research_events.jsonl": "9f632fd0e8b7f580799506fbd44a2ff06cfbc61833deb8b36284a902f26d44e6",
    "pyproject.toml": "fa4fb4e199979299d90d1f49fae9e4776c799242a4ce4706c7ee1f7f762258c5",
    "qbacktest/__init__.py": "e00b9d676bafb4a58dc9f033751459dd0447c8c4f75aa6288afd144fc98e5303",
    "qbacktest/baselines.py": "31f119195b3430050dc5a2874beae39e98672a5b124ae407c2e572ad36636fdc",
    "qbacktest/costs.py": "84d616603e21d92d82273f563fca92da7fc2cb6f4a4d319769946e5804a63a27",
    "qbacktest/engine.py": "effd6d6b5bfef616a386f050e2d27bf012aab881c571c47999e32aa208388ad0",
    "qbacktest/errors.py": "658bcf18369aa031775a4113d5b3e4ed3a7317e83eb0c07eb8ceb772dab87cd5",
    "qbacktest/metrics.py": "027fb780692f51a4274cefb9917f77bdce96523cdcdc54c8dc40ddcd87a3edeb",
    "qbacktest/models.py": "c9a90af5c48633a551cb5b27cc7a643a61cdd6a4db55a3191308917662e29397",
    "qresearch/__init__.py": "51e38a8fb6932bba9091d24c9803ba53fba037033f76c97c36d94b9c36c726d2",
    "qresearch/analysis.py": "da4ed2c04a756fb66c406ae6ba1112c610c55e2ec9b8ccd2105c3d94bdf7a9bf",
    "qresearch/csv_loader.py": "e522873d83319f09138f4ff77619ac47dea118c10f9cd12ffc32a5955fb116ba",
    "qresearch/errors.py": "97ef9e926f5acca36ba37ec59a897c52dc111f95b97f28529a81f31dec0751a7",
    "qresearch/indicators.py": "7acdea254bd84b91e5633d80b655490f63a5b44c74360b210d4901d789a43001",
    "qresearch/metrics.py": "96c842fdffb552fd3ddc6561ef41ae20a9c600c41ddb88ad810b70892c76d09f",
    "qresearch/models.py": "d21a46879fb7ba52227928d56e92becb564482bf93670777fd039c226d7b7e51",
    "qresearch/returns.py": "702c7c2aae1f41f32c45a9447442660912d0729b246d7805b22574299ea438f3",
    "qresearch/validation.py": "f76c7526726d5e2cf29f2c4ea2884aa32ee35ac2988ff629eeb16913e5bc934b",
    "uv.lock": "9f8ad20f3a59e6ccf1490cb8203cb26eec2f46ae944f9fc4cf2c4e68ab938a8b"
}
FROZEN_BASELINE_MANIFEST_SHA256 = "9ece313e2e83e8463078eac7abbef84e27151f8b90a3b32c796cb771f98663d1"
LIVE_BEFORE_SHA256 = {
    "block15/contract_v2.py": "2ce7280c42eb2284230002f69e1ccf5e54e224f81057ea1d75dc4894ec880c0e",
    "block15/order_v2_research.py": None,
    "mdl/__init__.py": "931cb0f8e0e77e20cd041d91645a5b3b150ab93b08ecbe578528f397cada5979",
    "mdl/agent.py": "4d0b99a2bd409d331889fd0e047283d3c1fe7da0a567cc25a4f3179f4dad7b0f",
    "mdl/cli.py": "b4f2724ce40609c47e505a0e64b574a5764b53ec99e4244097e0ed26feec03c5",
    "mdl/config.py": "790f74f1798877927298969ce727af2e30d7a162151904c03a61ba6e234923ff",
    "mdl/context_engine.py": "a10f747cbf6ed71ec03d5ab75e3c594356fd545b35bbf7033b9d239a5ac2b7a7",
    "mdl/errors.py": "7929341adc99875d91647436af10408a17b6c0ce9f0af7b345ad42d275db61b9",
    "mdl/expr_parser.py": "c66021d625a6b72b91e40e0832a7f4c73c4ccddbc7f497153db72bee351d2042",
    "mdl/logging_store.py": "241230ae874a71f5d4b58ebe30807579eb7237a06ca4e79fd9492c456e82e6cf",
    "mdl/ollama_client.py": "39702ab45b524af07c7bebd150722181a53d984a109b8a87463e5c6db7f1ce6a",
    "mdl/orchestrator.py": "71ae3b537cd2a1bef030cb99fc65f5bbe4d3e400b178e86bb10c557ca657ffce",
    "mdl/schemas.py": "42651da9826c99407fdb68f7ff0b8a79f922bc15d0b092025401e6e23f4cc959",
    "mdl/symbolic.py": "d8ab629fd0f8e4b3f0dde1059de9053ee8034be8870313ecd583549387c16f7c",
    "mdl/verifier.py": "d89c1617d8c773d588fb2a2790ac0158aa4b71af070b1364892b8e4476b8610f",
    "mdl/worker.py": "67760c4296b402dc4bf161aefa34e6bb000ffe142191226d662677afe81dc72e",
    "tests/_qbacktest_helpers.py": "35ec272e3819a7b430d9ef9d420b74360f30177a75aabdaa705dd691ee7bbd98",
    "tests/_qresearch_helpers.py": "0afa6d95d9aa73715fdfea267411f6881b77196b761aed31a7d4e9f1fb633fb4",
    "tests/conftest.py": "623c5574fce7aade11ea860b785416d3f3cc641a4c7b871b08e184bb4e8eefaa",
    "tests/test_agent_mock.py": "939e44755e4e5212d18b549fcb55c3c59831a56f5db3c6ff9bf13f941a206ed0",
    "tests/test_context_engine.py": "5fe70884adc2121893f49cac382ca4dec0102ffd0cea44a25058c8c1e336918a",
    "tests/test_contract_v2.py": "0a1c2c1ef726754b2c2d02f18646989f6290a839d13ac919e467dab8031944d2",
    "tests/test_e2e_live.py": "7d064340a0e1ea72fab55b11f0c4e18fcd7a904deb77c2cba0ad348d2354ed36",
    "tests/test_expr_parser.py": "47e15ff17649b2124dcd8924820efb235830a69e2630a2d568cd334cccf02172",
    "tests/test_logging_store.py": "bdbadafd9787dc6032c46ccdcc735fe97ea91c684e3e87c5121eab26e1e4c1e4",
    "tests/test_memory_pilot.py": "352876469b7ac10b022f487fedb08e48a2d32329ca271088774743ec266126b9",
    "tests/test_ollama_client.py": "f1cb50375f749ef8b00652558222f6dc57e453fae0270e8db13b6747875d1e61",
    "tests/test_orchestrator.py": "65ebb909b187265de75fe28681def323a13ef925abd5d627753ec88a3c391148",
    "tests/test_qbacktest_baselines.py": "5c8ce7fd8c8b16fa2d3d0f32a51827db965b40d9eafdfca6d38afe1474f0e642",
    "tests/test_qbacktest_costs.py": "f11e1d42e7ed76dedd2f386bef9068ebd4ccbe902be47111930d5b8950fa6ec2",
    "tests/test_qbacktest_engine.py": "c42ebdd3f291f156e15a250a084263287775a9a011733b47177fe61e263f2d91",
    "tests/test_qbacktest_metrics.py": "40dbd5fd9f8664c95ec001c9c6b62df5bcc7ca2b247e7bbeb36d27552aeda5b4",
    "tests/test_qbacktest_models.py": "7d44ddff1d1eb2be6ea4f0246055c99b25ba7510c5806f14cc21c7384e129999",
    "tests/test_qbacktest_scope_imports.py": "31a9676a680adbf47f51bd3ec6a724d841241fd968fddaf52e91212b4f85a25c",
    "tests/test_qresearch_analysis.py": "c144d0177f538d2e0b27cc813a8b5528f0c857a645e748ff0fecffcb6e510f1c",
    "tests/test_qresearch_calculations.py": "6ba10c9f5d0bc4926c0acee9418f6d001f02563d86bae44c663d98dbc9d63425",
    "tests/test_qresearch_csv_loader.py": "86c0d90f7b7c553b233802dcd024c72052b7e1baee637e9c25c5db5765aa9887",
    "tests/test_qresearch_models.py": "99a3b868516f88bb31a340c08548997e9a88b18937cd3ff3a91f9f59dfb81cc1",
    "tests/test_qresearch_scope_imports.py": "16a3e3d5f4c23cc12c221087304ddbaffaa8711ec775ae1174180f6d552b55d6",
    "tests/test_round4_qad_phase1.py": "65d09e1880f5905d348dfc5ec8dc3ef346323bfd88323a22cc71f229b1d0bb54",
    "tests/test_verifier.py": "90475ee0fea798772373c0a58a1a7655ef9ee521aa3c8b5eeb93f7a2ddaa7e60"
}
FROZEN_PROMPT_SHA256 = {
    "V2C01_coeff_x_plus_4_pow8_x5": "8cf0bffd8aaffe2f039f1df1363cf5cf28a85e05ec53501f5e794043e2a5fdb8",
    "V2C02_coeff_2x_minus_7_pow6_x4": "071ba1b05ba83eb6abb0bf9b31f1c196f9eb311f3e0105f6b153262a14f923d7",
    "V2C03_coeff_5x_minus_2_pow7_x3": "c3cdad1ad5a426b5359ae93f1f59f64d201a5ad7a4f4a5938c11fce29bbe2ff8",
    "V2C04_coeff_x_minus_6_pow9_x7": "ac2f1460b204c825a420d61c257cf6b872dd069c7278ccec2e3c63e2ab01a2aa",
    "V2C05_coeff_4x_plus_3_pow7_x2": "17c6b7ad4b476d9cd8e8950097c3095c5ada0d801fb88cf2c71dcdb3e9f1117c",
    "V2C06_coeff_7x_minus_2_pow6_x5": "c529aac0926640e7a81e58a8efda3cdab753442f6cb20eb8e3b26ff520206969",
    "V2C07_coeff_2x_plus_9_pow8_x6": "9fc917f5cd0341839056b1a661b63298c2cc5ad21fe88cbe48f65215c2d09b1a",
    "V2C08_coeff_3x_minus_5_pow8_x5": "97b3a1ab0c4dafc8c063e04d796b5baac12e61eb52656ca20a9355dfae1e316a",
    "V2C09_coeff_6x_plus_5_pow6_x2": "dfe7408f0e727823005659e7048358ac25b5ffc71a20c329329b1a17104789e9",
    "V2C10_coeff_x_plus_8_pow10_x8": "c2ddf63ea785a2ee4412e987e9585bd156448f421f99c0b8dbc1ee3072eacaa5",
    "V2C11_coeff_5x_plus_4_pow7_x3": "d4171bbf06a45b0e88c44e284ba550a6b3a754cfacab4aac96e80b2b1eabfc7c",
    "V2C12_coeff_4x_minus_7_pow6_x4": "881aa128e6305ecb300115dcb03f5f5f1d08349a11566e40680440de11e5315c",
    "V2C13_coeff_7x_plus_3_pow6_x3": "d7047bacb349842fe011d274d52ae36d4945f8a9613ce44663b9a24f26919012",
    "V2C14_coeff_3x_plus_6_pow8_x6": "d90464bd91a5b6c9a730d5ea6e1724a51a117045dcca794a7e5706a42f8e6d79",
    "V2C15_coeff_6x_minus_7_pow6_x2": "5b328f26874b6c8bc7c93fc0ee1b98ad0941f806718e017537c8c0cf81ace6ee",
    "V2M01_minimal_n2_plus_5n_plus_1217": "52ecd4f4d9d208fe42d5ec40c9aa0c25d2303aa3d45ae2660536954667dcdfdb",
    "V2M02_minimal_n2_plus_7n_plus_1163": "50ed0b6e45afba8ccf762356d864cb3edaa01ee9def3529b6caa2e9085eb11dc",
    "V2M03_minimal_n2_plus_5n_plus_1223": "50ec79311cfa903598f89f6eea21f2aec8640f3f9be8a47c24a037e988b71090",
    "V2M04_minimal_2n2_plus_6n_plus_1031": "f7623c70305c2390d1ffca221de3997d9d25537233564187f8b887eb4cc95f5b",
    "V2M05_minimal_4n2_plus_2n_plus_1013": "e579642629815a8f2c5b3992b0058c22d9973d53ba31ce08bc1bbc7303b9b27c",
    "V2M06_minimal_n2_plus_3n_plus_1429": "40cd8e517f29ee7e8f4c5c44b9fac88ba86dbaee773cd03473764542cd64a549",
    "V2M07_minimal_n2_plus_n_plus_1481": "ade78622a6b23f3c89f8cf9ff3290d0aa26303bc16c600191345d7de55980fca",
    "V2M08_minimal_n2_plus_n_plus_1487": "dd963deea7df734756430a2812ae90aae1a6ecf20fde0a18c99e8ee7458485da",
    "V2M09_minimal_3n2_plus_3n_plus_1033": "70e7ed85735fe2c12ad129ca9b25a4732b35d616c6f704410dab0a12be3901f8",
    "V2M10_minimal_2n2_plus_4n_plus_1483": "dc548ac83acf097effa9dae171dd2a2ecf82f1077beafc424aaaf1b1d4002a4e",
    "V2M11_minimal_4n2_plus_4n_plus_1163": "a328a7bc9dca161207029ef1fb9139f74687ee3096622d31111488cf233a1a86",
    "V2M12_minimal_5n2_plus_5n_plus_1021": "b1ff5050013cbbda2bd457b2f19785566cef5c9708f2ddb0f31c51de679b5733",
    "V2M13_minimal_2n2_plus_6n_plus_1193": "59f05bce6784b37a4818ee1b637fbefc7bccc082feff3b8d6955c2947dffd300",
    "V2M14_minimal_5n2_plus_5n_plus_1399": "c4da752b988941d90229fdf7223c3e3828ce4b0b94c0b30c68640434c92770ee",
    "V2M15_minimal_3n2_plus_3n_plus_1283": "4501b95f08d962d96884100e3a895dd2d220ee7dcf46112176f2874b6f9bccc7"
}
FROZEN_SCHEMA_SHA256 = {
    "answer_first": "e9c52676497c7cbd5a882aecdc23f602e1e432e3641155bd069d5b220267dbd1",
    "derivation_first": "7ca06e0060d04bd42c13ec7bf232404217acb0963f10f2af467cabe17ab7ef53"
}
FROZEN_GROUND_TRUTH_SHA256 = "b0c4d70424d6a678ca840c43bae66afee3116d2637e94ff072abc041743c95f0"
# --- END EMBEDDED BASELINE ---


# ---------------------------------------------------------------------------
# STEP 1b -- FROZEN / LIVE protected-manifest split
# ---------------------------------------------------------------------------

# FROZEN: pre-existing protected artifacts.  Files created by THIS block are
# excluded and reported separately as NEW artifacts, including this module,
# the pre-registration/report, the new tests and the new data stores/results.
_NEW_DATA_PREFIX = "block15_order_v2"
_NEW_DATA_PREFIXES = ("block15_order_v2", "block15_diagnosis", "block15_placebo", "block15_skill_tool", "block15_tool_transfer", "block15_m2", "block15_null_probe", "block15_integration")
_NEW_ROOT_FILES = frozenset({
    "PREREG_ORDER_V2.md", "REPORT_ORDER_V2.md",
    "PREREG_DIAGNOSIS.md", "REPORT_DIAGNOSIS.md",
    "PREREG_PLACEBO.md", "REPORT_PLACEBO.md",
    "PREREG_SKILL_TOOL.md", "REPORT_SKILL_TOOL.md",
    "PREREG_TOOL_TRANSFER.md", "REPORT_TOOL_TRANSFER.md",
    "PREREG_TOOL_TRANSFER_V2.md", "REPORT_TOOL_TRANSFER_V2.md",
    "PREREG_TOOL_TRANSFER_V3.md", "REPORT_TOOL_TRANSFER_V3.md",
    "PREREG_M2_CARD.md", "REPORT_M2_CARD.md",
    "PREREG_INTEGRATION.md", "REPORT_INTEGRATION.md", "REPORT_CONTRACT_A.md",
})
_FROZEN_EXACT_FILES = (
    "block15/ceiling_research.py",
    "block15/heldout_research.py",
    "block15/memory_pilot.py",
    "block15/tasks.py",
    "block15/run_benchmark.py",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
)
_FROZEN_RESEARCH_EXCLUDED = frozenset(
    {"ceiling_research.py", "heldout_research.py"}
)


def _relative_files(root: Path, pattern: str) -> list[str]:
    # Caches are volatile build artifacts, not protected source files.
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.glob(pattern)
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def frozen_paths(root: Path | None = None) -> list[str]:
    """Return the FROZEN manifest paths, sorted and de-duplicated."""
    root = root or DATA_DIR.parent
    paths: set[str] = set()
    # data/: only files that existed before this block.  New order_v2 stores
    # and results are NEW artifacts, not FROZEN files.
    paths.update(
        path
        for path in _relative_files(root, "data/*")
        if not any(Path(path).name.startswith(p) for p in _NEW_DATA_PREFIXES)
    )
    for pattern in ("BLOCK15_*.md", "PREREG_*.md", "REPORT_*.md", "README_*.md"):
        paths.update(p for p in _relative_files(root, pattern) if p not in _NEW_ROOT_FILES)
    paths.update(p for p in _FROZEN_EXACT_FILES if (root / p).is_file())
    paths.update(_relative_files(root, "block15/round*.py"))
    paths.update(_relative_files(root, "qresearch/**/*"))
    paths.update(_relative_files(root, "qbacktest/**/*"))
    return sorted(paths)


def live_paths(root: Path | None = None) -> list[str]:
    """Return the LIVE manifest paths, sorted and de-duplicated."""
    root = root or DATA_DIR.parent
    paths: set[str] = set(_relative_files(root, "mdl/**/*"))
    if (root / "block15/contract_v2.py").is_file():
        paths.add("block15/contract_v2.py")
    # Only NEW research modules are LIVE; the frozen ceiling/heldout research
    # modules keep their FROZEN classification.
    paths.update(
        p
        for p in _relative_files(root, "block15/*_research.py")
        if Path(p).name not in _FROZEN_RESEARCH_EXCLUDED
    )
    paths.update(_relative_files(root, "tests/**/*"))
    return sorted(paths)


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha256(path: Path, *, commit: str = "HEAD") -> str | None:
    """Additive helper: SHA-256 of a file's GIT BLOB bytes at ``commit``.

    Unlike ``_sha256_file`` (which hashes the worktree bytes, where Git with
    core.autocrlf=true stores CRLF), this hashes the canonical blob bytes that
    Git stores (LF).  This is the hash to record for source provenance so the
    value is independent of worktree line-ending conversion.  Returns None if
    the file is not tracked at that commit or Git is unavailable.
    """
    root = DATA_DIR.parent
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit}:{rel}"],
            capture_output=True,
            cwd=str(root),
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return hashlib.sha256(proc.stdout).hexdigest()


def module_git_blob_sha256() -> str | None:
    """SHA-256 of this module's committed GIT BLOB (line-ending invariant)."""
    return git_blob_sha256(Path(__file__))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(value: object, *, sort_keys: bool) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=sort_keys, separators=(",", ":")
    )


def _sha256_json(value: object, *, sort_keys: bool = True) -> str:
    return _sha256_text(_canonical_json(value, sort_keys=sort_keys))


def frozen_hashes(root: Path | None = None) -> dict[str, str | None]:
    root = root or DATA_DIR.parent
    return {p: _sha256_file(root / p) for p in frozen_paths(root)}


def live_hashes(root: Path | None = None) -> dict[str, str | None]:
    root = root or DATA_DIR.parent
    return {p: _sha256_file(root / p) for p in live_paths(root)}


def manifest_snapshot(root: Path | None = None) -> dict:
    """Baseline captured before generation; embedded in this module."""
    root = root or DATA_DIR.parent
    frozen = frozen_hashes(root)
    live = live_hashes(root)
    return {
        "frozen": frozen,
        "live": live,
        "frozen_path_count": len(frozen),
        "live_path_count": len(live),
        "frozen_manifest_sha256": _sha256_json(frozen),
    }


def verify_protected(root: Path | None = None) -> dict:
    """Compare current hashes with the embedded baseline constants."""
    root = root or DATA_DIR.parent
    current_frozen = frozen_hashes(root)
    current_live = live_hashes(root)
    frozen_diff = {
        p: {"before": before, "after": current_frozen.get(p)}
        for p, before in FROZEN_BASELINE_SHA256.items()
        if before != current_frozen.get(p)
    }
    live_rows = {
        p: {
            "before": LIVE_BEFORE_SHA256.get(p),
            "after": current_live.get(p),
            "status": (
                "new"
                if LIVE_BEFORE_SHA256.get(p) is None
                else "changed"
                if LIVE_BEFORE_SHA256.get(p) != current_live.get(p)
                else "unchanged"
            ),
        }
        for p in sorted(set(current_live) | set(LIVE_BEFORE_SHA256))
    }
    return {
        "frozen_path_count": len(current_frozen),
        "frozen_baseline_path_count": len(FROZEN_BASELINE_SHA256),
        "frozen_byte_identical": not frozen_diff,
        "frozen_differences": frozen_diff,
        "frozen_manifest_sha256": _sha256_json(current_frozen),
        "frozen_baseline_manifest_sha256": FROZEN_BASELINE_MANIFEST_SHA256,
        "live_rows": live_rows,
    }


# ---------------------------------------------------------------------------
# Frozen tasks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderV2Task:
    id: str
    kind: str  # "coefficient" | "minimality"
    question: str
    prompt: str
    expected_display: str
    expression: str | None = None
    power: int | None = None
    expected_coefficient: int | None = None
    a: int | None = None
    b: int | None = None
    c: int | None = None
    expected_n: int | None = None
    expected_value: int | None = None
    expected_primes: tuple[int, ...] | None = None

    def metadata(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "question": self.question,
            "prompt": self.prompt,
            "prompt_sha256": _sha256_text(self.prompt),
            "expected_display": self.expected_display,
            "expression": self.expression,
            "power": self.power,
            "coefficient": self.expected_coefficient,
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "n": self.expected_n,
            "value": self.expected_value,
            "primes": list(self.expected_primes)
            if self.expected_primes is not None
            else None,
        }


def _task(
    *,
    id: str,
    kind: str,
    question: str,
    expected_display: str,
    **kwargs: object,
) -> OrderV2Task:
    return OrderV2Task(
        id=id,
        kind=kind,
        question=question,
        prompt=question + EFFECTIVE_INSTRUCTION_V2,
        expected_display=expected_display,
        **kwargs,
    )


TASKS: tuple[OrderV2Task, ...] = (
    # -- 15 fresh coefficient-extraction tasks -----------------------------
    _task(
        id="V2C01_coeff_x_plus_4_pow8_x5",
        kind="coefficient",
        question=(
            "Expand (x + 4)^8 and report the coefficient of x^5. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="3584",
        expression="(x + 4)**8",
        power=5,
        expected_coefficient=3584,
    ),
    _task(
        id="V2C02_coeff_2x_minus_7_pow6_x4",
        kind="coefficient",
        question=(
            "Expand (2x - 7)^6 and report the coefficient of x^4. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="11760",
        expression="(2*x - 7)**6",
        power=4,
        expected_coefficient=11760,
    ),
    _task(
        id="V2C03_coeff_5x_minus_2_pow7_x3",
        kind="coefficient",
        question=(
            "Expand (5x - 2)^7 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="70000",
        expression="(5*x - 2)**7",
        power=3,
        expected_coefficient=70000,
    ),
    _task(
        id="V2C04_coeff_x_minus_6_pow9_x7",
        kind="coefficient",
        question=(
            "Expand (x - 6)^9 and report the coefficient of x^7. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="1296",
        expression="(x - 6)**9",
        power=7,
        expected_coefficient=1296,
    ),
    _task(
        id="V2C05_coeff_4x_plus_3_pow7_x2",
        kind="coefficient",
        question=(
            "Expand (4x + 3)^7 and report the coefficient of x^2. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="81648",
        expression="(4*x + 3)**7",
        power=2,
        expected_coefficient=81648,
    ),
    _task(
        id="V2C06_coeff_7x_minus_2_pow6_x5",
        kind="coefficient",
        question=(
            "Expand (7x - 2)^6 and report the coefficient of x^5. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-201684",
        expression="(7*x - 2)**6",
        power=5,
        expected_coefficient=-201684,
    ),
    _task(
        id="V2C07_coeff_2x_plus_9_pow8_x6",
        kind="coefficient",
        question=(
            "Expand (2x + 9)^8 and report the coefficient of x^6. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="145152",
        expression="(2*x + 9)**8",
        power=6,
        expected_coefficient=145152,
    ),
    _task(
        id="V2C08_coeff_3x_minus_5_pow8_x5",
        kind="coefficient",
        question=(
            "Expand (3x - 5)^8 and report the coefficient of x^5. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="-1701000",
        expression="(3*x - 5)**8",
        power=5,
        expected_coefficient=-1701000,
    ),
    _task(
        id="V2C09_coeff_6x_plus_5_pow6_x2",
        kind="coefficient",
        question=(
            "Expand (6x + 5)^6 and report the coefficient of x^2. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="337500",
        expression="(6*x + 5)**6",
        power=2,
        expected_coefficient=337500,
    ),
    _task(
        id="V2C10_coeff_x_plus_8_pow10_x8",
        kind="coefficient",
        question=(
            "Expand (x + 8)^10 and report the coefficient of x^8. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="2880",
        expression="(x + 8)**10",
        power=8,
        expected_coefficient=2880,
    ),
    _task(
        id="V2C11_coeff_5x_plus_4_pow7_x3",
        kind="coefficient",
        question=(
            "Expand (5x + 4)^7 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="1120000",
        expression="(5*x + 4)**7",
        power=3,
        expected_coefficient=1120000,
    ),
    _task(
        id="V2C12_coeff_4x_minus_7_pow6_x4",
        kind="coefficient",
        question=(
            "Expand (4x - 7)^6 and report the coefficient of x^4. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="188160",
        expression="(4*x - 7)**6",
        power=4,
        expected_coefficient=188160,
    ),
    _task(
        id="V2C13_coeff_7x_plus_3_pow6_x3",
        kind="coefficient",
        question=(
            "Expand (7x + 3)^6 and report the coefficient of x^3. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="185220",
        expression="(7*x + 3)**6",
        power=3,
        expected_coefficient=185220,
    ),
    _task(
        id="V2C14_coeff_3x_plus_6_pow8_x6",
        kind="coefficient",
        question=(
            "Expand (3x + 6)^8 and report the coefficient of x^6. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="734832",
        expression="(3*x + 6)**8",
        power=6,
        expected_coefficient=734832,
    ),
    _task(
        id="V2C15_coeff_6x_minus_7_pow6_x2",
        kind="coefficient",
        question=(
            "Expand (6x - 7)^6 and report the coefficient of x^2. "
            "Give the exact integer coefficient, including its sign."
        ),
        expected_display="1296540",
        expression="(6*x - 7)**6",
        power=2,
        expected_coefficient=1296540,
    ),
    # -- 15 fresh bounded-minimality tasks ---------------------------------
    _task(
        id="V2M01_minimal_n2_plus_5n_plus_1217",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 5n + 1217. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1241 = 17 * 73",
        a=1,
        b=5,
        c=1217,
        expected_n=3,
        expected_value=1241,
        expected_primes=(17, 73),
    ),
    _task(
        id="V2M02_minimal_n2_plus_7n_plus_1163",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 7n + 1163. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1207 = 17 * 71",
        a=1,
        b=7,
        c=1163,
        expected_n=4,
        expected_value=1207,
        expected_primes=(17, 71),
    ),
    _task(
        id="V2M03_minimal_n2_plus_5n_plus_1223",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 5n + 1223. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1247 = 29 * 43",
        a=1,
        b=5,
        c=1223,
        expected_n=3,
        expected_value=1247,
        expected_primes=(29, 43),
    ),
    _task(
        id="V2M04_minimal_2n2_plus_6n_plus_1031",
        kind="minimality",
        question=(
            "Let f(n) = 2n^2 + 6n + 1031. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1067 = 11 * 97",
        a=2,
        b=6,
        c=1031,
        expected_n=3,
        expected_value=1067,
        expected_primes=(11, 97),
    ),
    _task(
        id="V2M05_minimal_4n2_plus_2n_plus_1013",
        kind="minimality",
        question=(
            "Let f(n) = 4n^2 + 2n + 1013. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1055 = 5 * 211",
        a=4,
        b=2,
        c=1013,
        expected_n=3,
        expected_value=1055,
        expected_primes=(5, 211),
    ),
    _task(
        id="V2M06_minimal_n2_plus_3n_plus_1429",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + 3n + 1429. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1457 = 31 * 47",
        a=1,
        b=3,
        c=1429,
        expected_n=4,
        expected_value=1457,
        expected_primes=(31, 47),
    ),
    _task(
        id="V2M07_minimal_n2_plus_n_plus_1481",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + n + 1481. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1501 = 19 * 79",
        a=1,
        b=1,
        c=1481,
        expected_n=4,
        expected_value=1501,
        expected_primes=(19, 79),
    ),
    _task(
        id="V2M08_minimal_n2_plus_n_plus_1487",
        kind="minimality",
        question=(
            "Let f(n) = n^2 + n + 1487. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1507 = 11 * 137",
        a=1,
        b=1,
        c=1487,
        expected_n=4,
        expected_value=1507,
        expected_primes=(11, 137),
    ),
    _task(
        id="V2M09_minimal_3n2_plus_3n_plus_1033",
        kind="minimality",
        question=(
            "Let f(n) = 3n^2 + 3n + 1033. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 6, f(n) = 1159 = 19 * 61",
        a=3,
        b=3,
        c=1033,
        expected_n=6,
        expected_value=1159,
        expected_primes=(19, 61),
    ),
    _task(
        id="V2M10_minimal_2n2_plus_4n_plus_1483",
        kind="minimality",
        question=(
            "Let f(n) = 2n^2 + 4n + 1483. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1513 = 17 * 89",
        a=2,
        b=4,
        c=1483,
        expected_n=3,
        expected_value=1513,
        expected_primes=(17, 89),
    ),
    _task(
        id="V2M11_minimal_4n2_plus_4n_plus_1163",
        kind="minimality",
        question=(
            "Let f(n) = 4n^2 + 4n + 1163. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1211 = 7 * 173",
        a=4,
        b=4,
        c=1163,
        expected_n=3,
        expected_value=1211,
        expected_primes=(7, 173),
    ),
    _task(
        id="V2M12_minimal_5n2_plus_5n_plus_1021",
        kind="minimality",
        question=(
            "Let f(n) = 5n^2 + 5n + 1021. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 3, f(n) = 1081 = 23 * 47",
        a=5,
        b=5,
        c=1021,
        expected_n=3,
        expected_value=1081,
        expected_primes=(23, 47),
    ),
    _task(
        id="V2M13_minimal_2n2_plus_6n_plus_1193",
        kind="minimality",
        question=(
            "Let f(n) = 2n^2 + 6n + 1193. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 5, f(n) = 1273 = 19 * 67",
        a=2,
        b=6,
        c=1193,
        expected_n=5,
        expected_value=1273,
        expected_primes=(19, 67),
    ),
    _task(
        id="V2M14_minimal_5n2_plus_5n_plus_1399",
        kind="minimality",
        question=(
            "Let f(n) = 5n^2 + 5n + 1399. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 7, f(n) = 1679 = 23 * 73",
        a=5,
        b=5,
        c=1399,
        expected_n=7,
        expected_value=1679,
        expected_primes=(23, 73),
    ),
    _task(
        id="V2M15_minimal_3n2_plus_3n_plus_1283",
        kind="minimality",
        question=(
            "Let f(n) = 3n^2 + 3n + 1283. Find the smallest integer n >= 0 "
            "such that f(n) is composite. Give n, the value f(n), and the "
            "complete prime factorization of f(n)."
        ),
        expected_display="n = 4, f(n) = 1343 = 17 * 79",
        a=3,
        b=3,
        c=1283,
        expected_n=4,
        expected_value=1343,
        expected_primes=(17, 79),
    ),
)


# ---------------------------------------------------------------------------
# SymPy ground truth, audit and copy guard
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"(?<![\d.])-?\d+(?!\d|\.\d)")


def extract_answer_ints(text: str) -> list[int]:
    normalized = text.replace("\u2212", "-").replace("\u2013", "-")
    normalized = re.sub(r"(?<=\d),(?=\d)", "", normalized)
    return sorted({int(match.group(0)) for match in _INT_RE.finditer(normalized)})


def _normalize_minimality_answer(text: str) -> str:
    normalized = re.sub(r"\^\s*\{?1\}?(?!\d)", "", text)
    normalized = re.sub(r"\*\*\s*1(?!\d)", "", normalized)
    return normalized


def _is_composite(value: int) -> bool:
    return value > 1 and not sympy.isprime(value)


def ground_truth(task: OrderV2Task) -> dict:
    """Compute and verify ground truth directly with SymPy."""
    if task.kind == "coefficient":
        if task.expression is None or task.power is None:
            raise ValueError(f"incomplete coefficient task: {task.id}")
        x = sympy.Symbol("x")
        coefficient = int(
            sympy.expand(sympy.sympify(task.expression)).coeff(x, task.power)
        )
        if coefficient != task.expected_coefficient:
            raise SystemExit(
                f"SymPy coefficient mismatch for {task.id}: "
                f"{coefficient} != {task.expected_coefficient}"
            )
        return {
            "kind": "coefficient",
            "expression": task.expression,
            "power": task.power,
            "coefficient": coefficient,
            "answer_tokens": [coefficient],
        }

    if any(v is None for v in (task.a, task.b, task.c)):
        raise ValueError(f"incomplete minimality task: {task.id}")
    first: tuple[int, int, dict[int, int]] | None = None
    for n in range(0, 201):
        value = int(task.a) * n * n + int(task.b) * n + int(task.c)
        if _is_composite(value):
            first = (n, value, sympy.factorint(value))
            break
    if first is None:
        raise SystemExit(f"no composite found for {task.id} within 0..200")
    n, value, factor = first
    primes = tuple(sorted(int(prime) for prime in factor))
    if any(int(exponent) != 1 for exponent in factor.values()):
        raise SystemExit(f"minimality task {task.id} is not squarefree: {factor}")
    if (
        n != task.expected_n
        or value != task.expected_value
        or primes != task.expected_primes
    ):
        raise SystemExit(
            f"SymPy minimality mismatch for {task.id}: "
            f"{(n, value, primes)} != "
            f"{(task.expected_n, task.expected_value, task.expected_primes)}"
        )
    return {
        "kind": "minimality",
        "a": task.a,
        "b": task.b,
        "c": task.c,
        "n": n,
        "value": value,
        "factorization": {
            str(prime): int(exp) for prime, exp in sorted(factor.items())
        },
        "primes": list(primes),
        "answer_tokens": [n, value, *primes],
    }


def ground_truth_manifest() -> dict[str, dict]:
    return {task.id: ground_truth(task) for task in TASKS}


def audit_answer(task: OrderV2Task, truth: dict, answer_text: str | None) -> dict:
    """Primary-endpoint audit from the final_answer text alone.

    Coefficient: the exact SymPy coefficient is present among the extracted
    integers.  Minimality: n, the composite value and both prime factors are
    all present, and SymPy independently verifies the factorization.
    Confidence value and schema validity never enter this audit.
    """
    if not isinstance(answer_text, str):
        return {
            "method": "no_answer_text",
            "audit_passed": False,
            "answer_tokens": [],
        }
    normalized = (
        _normalize_minimality_answer(answer_text)
        if truth["kind"] == "minimality"
        else answer_text
    )
    values = extract_answer_ints(normalized)
    value_set = set(values)
    if truth["kind"] == "coefficient":
        coefficient = int(truth["coefficient"])
        present = coefficient in value_set
        return {
            "method": "sympy_expand_coeff",
            "expected_coefficient": coefficient,
            "extracted_ints": values,
            "exact_value_present": bool(present),
            "strict_single_int": values == [coefficient],
            "audit_passed": bool(present),
        }

    n = int(truth["n"])
    value = int(truth["value"])
    primes = [int(p) for p in truth["primes"]]
    required = {n, value, *primes}
    present = required.issubset(value_set)
    factor = sympy.factorint(value)
    factor_primes = sorted(int(p) for p in factor)
    exponents_one = all(int(exp) == 1 for exp in factor.values())
    product_ok = int(
        sympy.prod(int(p) ** int(exp) for p, exp in factor.items())
    ) == value
    factorization_ok = (
        factor_primes == primes and exponents_one and product_ok
    )
    return {
        "method": "sympy_first_composite_and_factorint",
        "expected_n": n,
        "expected_value": value,
        "expected_primes": primes,
        "extracted_ints": values,
        "all_required_tokens_present": bool(present),
        "strict_set_equal": value_set == required,
        "sympy_factorization_verified": bool(factorization_ok),
        "audit_passed": bool(present and factorization_ok),
    }


def copy_possible(task: OrderV2Task, truth: dict) -> dict:
    hits = {
        str(token): bool(_number_present(task.prompt, int(token)))
        for token in truth["answer_tokens"]
    }
    return {
        "tokens_checked": list(hits),
        "token_present_in_prompt": hits,
        "copy_possible": bool(any(hits.values())),
    }


def _assert_no_copy() -> dict[str, dict]:
    truth = ground_truth_manifest()
    checks = {task.id: copy_possible(task, truth[task.id]) for task in TASKS}
    bad = [task_id for task_id, c in checks.items() if c["copy_possible"]]
    if bad:
        raise SystemExit(f"ground-truth token present in prompt for: {bad}")
    return checks


def _verify_frozen() -> dict:
    prompts = {t.id: _sha256_text(t.prompt) for t in TASKS}
    truth = ground_truth_manifest()
    schemas = {
        arm: _sha256_json(SCHEMAS[arm], sort_keys=False) for arm in ARMS
    }
    if prompts != FROZEN_PROMPT_SHA256:
        raise SystemExit("frozen prompt hashes do not match embedded constants")
    if schemas != FROZEN_SCHEMA_SHA256:
        raise SystemExit("frozen schema hashes do not match embedded constants")
    if _sha256_json(truth) != FROZEN_GROUND_TRUTH_SHA256:
        raise SystemExit("ground-truth manifest hash does not match constant")
    instruction = EFFECTIVE_INSTRUCTION_V2
    if not instruction.startswith(OUTPUT_INSTRUCTION_V2):
        raise SystemExit("effective instruction lost the neutral base")
    if instruction[len(OUTPUT_INSTRUCTION_V2) :].strip() != SCHEMA_ORDER_SENTENCE:
        raise SystemExit("effective instruction has extra text beyond one sentence")
    return {
        "prompts": prompts,
        "schemas": schemas,
        "ground_truth_manifest": _sha256_json(truth),
        "instruction_sha256": _sha256_text(instruction),
        "system_prompt_sha256": _sha256_text(SYSTEM_PROMPT_V2),
    }


# ---------------------------------------------------------------------------
# Fresh raw parse (never re-serialized)
# ---------------------------------------------------------------------------


def fresh_parse(raw_content: str | None) -> dict | None:
    """Parse raw_content from scratch, preserving the wire key order."""
    if not isinstance(raw_content, str) or not raw_content.strip():
        return None
    text = raw_content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class GuardStop(RuntimeError):
    """A pre-registered call, runtime or memory guard stopped the run."""


def _settings() -> Settings:
    return load_settings(
        model=MODEL,
        db_path=DATA_DIR / STORE_DB_NAME,
        jsonl_path=DATA_DIR / STORE_JSONL_NAME,
        context_limit=NUM_CTX,
        think=THINK,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        repeat_penalty=REPEAT_PENALTY,
        seed=SEED,
        keep_alive=KEEP_ALIVE,
    )


def _verify_model(client: OllamaClient) -> tuple[str, dict]:
    if not client.health():
        raise SystemExit("Ollama is not reachable")
    info = client.model_info()
    if info is None:
        raise SystemExit(f"model {MODEL!r} is not installed")
    digest = info.get("digest")
    if digest != MODEL_DIGEST:
        raise SystemExit(f"model digest mismatch: {digest!r}")
    details = info.get("details") or {}
    if details.get("quantization_level") != QUANTIZATION:
        raise SystemExit(
            f"quantization mismatch: {details.get('quantization_level')!r}"
        )
    return str(digest), info


def _failure_flags(row: dict) -> list[str]:
    """Multi-label failure flags; one cell can fail in several ways."""
    flags: list[str] = []
    if row.get("status") in {"timeout", "model_error", "error", "output_error"}:
        flags.append("call_error")
    if not row.get("parseable"):
        flags.append("parse_failed")
    if row.get("parseable") and not row.get("validate_v2_ok"):
        flags.append("schema_violation")
    if row.get("done_reason") == "length":
        flags.append("truncated")
    if not row.get("audit_passed"):
        flags.append("primary_wrong")
    conf = row.get("confidence_raw")
    if not (
        isinstance(conf, (int, float))
        and not isinstance(conf, bool)
        and 0.0 <= float(conf) <= 1.0
    ):
        flags.append("confidence_out_of_range")
    if row.get("copy_possible"):
        flags.append("copy_possible")
    return flags


def _truncation_invalid(row: dict) -> bool:
    return row.get("done_reason") == "length" and (
        not row.get("parseable") or not row.get("validate_v2_ok")
    )


def _failure_mode(row: dict) -> str:
    """Mutually exclusive failure mode for the partition table."""
    if row.get("status") in {"timeout", "model_error", "error", "output_error"}:
        return row["status"]
    if not row.get("parseable"):
        return "invalid_json"
    if not row.get("validate_v2_ok"):
        return (
            "truncated_invalid"
            if row.get("done_reason") == "length"
            else "contract_violation"
        )
    if row.get("done_reason") == "length":
        return "truncated_valid"
    if row.get("audit_passed"):
        return "primary_correct"
    return "primary_wrong"


class OrderV2Runner:
    def __init__(
        self,
        client: OllamaClient,
        store: ResearchStore,
        digest: str,
        model_info: dict,
        run_id: str,
        copy_checks: dict[str, dict],
    ) -> None:
        self.client = client
        self.store = store
        self.digest = digest
        self.model_info = model_info
        self.run_id = run_id
        self.copy_checks = copy_checks
        self.started = perf_counter()
        self.calls_used = 0
        self.free_mb_min: float | None = None

    @property
    def elapsed_s(self) -> float:
        return perf_counter() - self.started

    def _guard(self) -> None:
        if self.calls_used + 1 > MAX_CALLS:
            raise GuardStop(f"cumulative call budget {MAX_CALLS} reached")
        if self.elapsed_s >= MAX_RUNTIME_S:
            raise GuardStop(
                f"cumulative runtime budget {MAX_RUNTIME_S:.0f}s reached"
            )
        free = free_physical_mb()
        if free is not None:
            if self.free_mb_min is None or free < self.free_mb_min:
                self.free_mb_min = free
            if free < MIN_FREE_MB:
                raise GuardStop(
                    f"free physical memory {free:.1f} MB below {MIN_FREE_MB:.0f} MB"
                )

    def run_cell(self, arm: str, task: OrderV2Task, truth: dict) -> dict:
        self._guard()
        self.calls_used += 1
        call_index = self.calls_used
        own_schema = SCHEMAS[arm]
        other_schema = SCHEMAS["derivation_first" if arm == "answer_first" else "answer_first"]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_V2},
            {"role": "user", "content": task.prompt},
        ]
        started = perf_counter()
        response = None
        raw_content: str | None = None
        done_reason: str | None = None
        prompt_eval_count: int | None = None
        eval_count: int | None = None
        protocol_variant = "unknown"
        schema_enforced: bool | None = None
        think_sent: bool | None = None
        status = "error"
        error: str | None = None

        try:
            response = self.client.chat_json(
                messages, own_schema, num_predict=NUM_PREDICT
            )
            raw_content = response.content
            done_reason = response.done_reason
            prompt_eval_count = response.prompt_eval_count
            eval_count = response.eval_count
            protocol_variant = response.protocol_variant
            schema_enforced = response.schema_enforced
            think_sent = response.think_sent
            status = "ok"
        except ModelOutputError as exc:
            raw_content = exc.raw_content
            done_reason = exc.done_reason
            prompt_eval_count = exc.prompt_eval_count
            eval_count = exc.eval_count
            protocol_variant = exc.protocol_variant
            schema_enforced = exc.schema_enforced
            think_sent = exc.think_sent
            error = f"{type(exc).__name__}: {exc}"
            status = "output_error"
        except ModelTimeoutError as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = "timeout"
        except ModelError as exc:
            error = f"{type(exc).__name__}: {exc}"
            status = "model_error"
        except Exception as exc:  # noqa: BLE001 - transport failures are data
            error = f"{type(exc).__name__}: {exc}"
            status = "error"

        latency_ms = (perf_counter() - started) * 1000.0
        parsed = fresh_parse(raw_content)
        parseable = parsed is not None
        if parsed is not None:
            provenance = emission_order_provenance(parsed, own_schema, other_schema)
            emitted = list(provenance["emitted_key_order"])
            matches_own = bool(provenance["matches_own_schema"])
            matches_other = bool(provenance["matches_other_schema"])
            ok, violations = validate_v2(parsed, own_schema)
            validate_ok, validate_violations = bool(ok), list(violations)
            answer_text = parsed.get("final_answer")
            confidence_raw = parsed.get("confidence")
        else:
            emitted, matches_own, matches_other = [], False, False
            validate_ok, validate_violations = False, ["response is not a parseable JSON object"]
            answer_text = None
            confidence_raw = None

        audit = audit_answer(task, truth, answer_text)
        copied = self.copy_checks[task.id]
        row = {
            "call_index": call_index,
            "task_id": task.id,
            "task_kind": task.kind,
            "arm": arm,
            "status": status,
            "error": error,
            "prompt_sha256": _sha256_text(task.prompt),
            "schema_sha256": _sha256_json(own_schema, sort_keys=False),
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
            "raw_content": raw_content,
            "raw_content_sha256": (
                _sha256_text(raw_content) if raw_content is not None else None
            ),
            # per-cell provenance required by the pre-registration
            "emitted_key_order": emitted,
            "matches_own_schema": matches_own,
            "matches_other_schema": matches_other,
            "validate_v2_ok": validate_ok,
            "validate_v2_violations": validate_violations,
            "protocol_variant": protocol_variant,
            "schema_enforced": schema_enforced,
            "think_sent": think_sent,
            "done_reason": done_reason,
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
            "confidence_raw": confidence_raw,
            "copy_possible": bool(copied["copy_possible"]),
            "copy_detail": copied,
            "latency_ms": round(latency_ms, 2),
            "parseable": parseable,
            "answer_text": answer_text,
            "audit": audit,
            "audit_passed": bool(audit["audit_passed"]),
            "primary_correct": bool(audit["audit_passed"]) and not copied["copy_possible"],
        }
        row["failure_flags"] = _failure_flags(row)
        row["failure_mode"] = _failure_mode(row)
        row["truncation_invalid"] = _truncation_invalid(row)
        self.store.log_step(
            self.run_id,
            "order_v2_cell",
            row["failure_mode"],
            row,
            latency_ms=latency_ms,
        )
        print(
            f"    {arm:<16} {task.id:<42} mode={row['failure_mode']:<18} "
            f"primary={row['primary_correct']} own={matches_own} "
            f"other={matches_other} done={done_reason} "
            f"eval={eval_count} latency_s={latency_ms / 1000:.1f}",
            flush=True,
        )
        return row


def run_study() -> Path:
    if sorted(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")):
        raise SystemExit("refusing to rerun: order_v2 result files already exist")
    frozen = _verify_frozen()
    protected = verify_protected()
    if not protected["frozen_byte_identical"]:
        raise SystemExit("FROZEN artifacts changed; refusing to generate")
    truth_manifest = ground_truth_manifest()
    copy_checks = _assert_no_copy()

    settings = _settings()
    settings.ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path_by_arm = {
        arm: DATA_DIR / f"{RESULTS_PREFIX}{arm}_{ts}.json" for arm in ARMS
    }
    for path in path_by_arm.values():
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    client = OllamaClient(settings)
    store = ResearchStore(settings.db_path, settings.jsonl_path)
    common: dict = {
        "kind": "order_v2_final_answer_position",
        "started_at": _now(),
        "model": MODEL,
        "frozen_verification": frozen,
        "protected_manifest": protected,
        "ground_truth_manifest": truth_manifest,
        "copy_checks": copy_checks,
        "settings": {
            "think": THINK,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "repeat_penalty": REPEAT_PENALTY,
            "seed": SEED,
            "keep_alive": KEEP_ALIVE,
            "system_prompt_sha256": frozen["system_prompt_sha256"],
            "instruction_sha256": frozen["instruction_sha256"],
            "effective_instruction": EFFECTIVE_INSTRUCTION_V2,
            "added_sentence": SCHEMA_ORDER_SENTENCE,
        },
        "arms": {
            arm: {
                "schema": SCHEMAS[arm],
                "schema_sha256": frozen["schemas"][arm],
            }
            for arm in ARMS
        },
        "guards": {
            "max_calls": MAX_CALLS,
            "max_runtime_s": MAX_RUNTIME_S,
            "min_free_mb": MIN_FREE_MB,
            "planned_calls": PLANNED_CALLS,
        },
        "planned_calls": PLANNED_CALLS,
        "free_mb_start": free_physical_mb(),
        "free_mb_min": None,
        "free_mb_end": None,
        "calls_used_total": 0,
        "runtime_s_total": 0.0,
        "stopped_early": False,
        "stop_reason": None,
    }
    try:
        digest, model_info = _verify_model(client)
        common["model_digest"] = digest
        common["model_info"] = model_info
        # Additive: record the module's Git blob hash (line-ending invariant)
        # in every result file so each arm can be tied to the exact source.
        common["module_git_blob_sha256"] = module_git_blob_sha256()
        experiment_id = store.create_experiment(
            seed=str(SEED),
            model=MODEL,
            model_digest=digest,
            parameters={
                "run_id": f"order_v2_{ts}",
                "kind": "order_v2_final_answer_position",
                "arms": list(ARMS),
                "planned_calls": PLANNED_CALLS,
                "num_predict": NUM_PREDICT,
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "repeat_penalty": REPEAT_PENALTY,
                "seed": SEED,
            },
            context_limit=NUM_CTX,
        )
        common["experiment_id"] = experiment_id
        runner = OrderV2Runner(
            client, store, digest, model_info, experiment_id, copy_checks
        )
        for arm in ARMS:
            record = dict(common)
            record.update(
                {
                    "run_id": f"order_v2_{arm}_{ts}",
                    "arm": arm,
                    "results": [],
                }
            )
            store.log_event(
                experiment_id,
                "order_v2_arm_started",
                {"arm": arm, "tasks": [t.id for t in TASKS]},
            )
            for index, task in enumerate(TASKS, start=1):
                print(
                    f"[{arm} {index}/{len(TASKS)}] {task.id} "
                    f"calls={runner.calls_used} elapsed_s={runner.elapsed_s:.1f}",
                    flush=True,
                )
                try:
                    row = runner.run_cell(arm, task, truth_manifest[task.id])
                except GuardStop as exc:
                    record["stopped_early"] = True
                    record["stop_reason"] = str(exc)
                    print(f"STOP: {exc}", flush=True)
                    break
                record["results"].append(row)
            record["calls_used_total"] = len(record["results"])
            record["runtime_s_total"] = round(runner.elapsed_s, 2)
            record["free_mb_min"] = runner.free_mb_min
            record["free_mb_end"] = free_physical_mb()
            record["finished_at"] = _now()
            record["protected_manifest_end"] = verify_protected()
            path_by_arm[arm].write_text(
                json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8"
            )
            print(
                f"arm {arm} complete: {path_by_arm[arm].name} "
                f"cells={len(record['results'])} "
                f"stopped_early={record['stopped_early']}",
                flush=True,
            )
            if record["stopped_early"]:
                break
    finally:
        runner_free = runner.free_mb_min if "runner" in locals() else None
        common["free_mb_min"] = runner_free
        client.close()
        store.close()
    print(f"results: {sorted(p.name for p in path_by_arm.values())}", flush=True)
    return path_by_arm[ARMS[-1]]


# ---------------------------------------------------------------------------
# Read-only analysis
# ---------------------------------------------------------------------------


def _mcnemar_exact(b: int, c: int) -> float:
    total = b + c
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(min(b, c) + 1))
    return min(1.0, 2.0 * tail / (2**total))


def _bootstrap_risk_difference(
    first: list[bool], second: list[bool], *, seed: int = 42, iterations: int = 10000
) -> list[float] | None:
    if not first or len(first) != len(second):
        return None
    rng = random.Random(seed)
    n = len(first)
    diffs = [int(second[i]) - int(first[i]) for i in range(n)]
    estimates: list[float] = []
    for _ in range(iterations):
        estimates.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    estimates.sort()
    return [
        round(estimates[int(0.025 * (iterations - 1))], 4),
        round(estimates[int(0.975 * (iterations - 1))], 4),
    ]


def _load_arm_results() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for path in sorted(DATA_DIR.glob(f"{RESULTS_PREFIX}*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        arm = record.get("arm")
        if arm not in ARMS:
            raise SystemExit(f"unexpected arm {arm!r} in {path.name}")
        if arm in records:
            raise SystemExit(f"multiple result files for arm {arm!r}")
        record["_path"] = path.name
        records[arm] = record
    return records


def summarize() -> dict:
    records = _load_arm_results()
    rows = {
        arm: {row["task_id"]: row for row in records[arm]["results"]}
        for arm in ARMS
        if arm in records
    }
    arm_stats: dict[str, dict] = {}
    for arm in ARMS:
        arm_rows = list(rows.get(arm, {}).values())
        parseable = [r for r in arm_rows if r["parseable"]]
        n_parse = len(parseable)
        own = sum(1 for r in parseable if r["matches_own_schema"])
        other = sum(1 for r in parseable if r["matches_other_schema"])
        n = len(arm_rows)
        trunc_invalid = sum(1 for r in arm_rows if r["truncation_invalid"])
        trunc_any = sum(1 for r in arm_rows if r["done_reason"] == "length")
        primary = sum(1 for r in arm_rows if r["primary_correct"])
        contract_ok = sum(1 for r in arm_rows if r["validate_v2_ok"])
        modes: dict[str, int] = {}
        for r in arm_rows:
            modes[r["failure_mode"]] = modes.get(r["failure_mode"], 0) + 1
        flags: dict[str, int] = {}
        for r in arm_rows:
            for flag in r["failure_flags"]:
                flags[flag] = flags.get(flag, 0) + 1
        arm_stats[arm] = {
            "present": arm in records,
            "path": records[arm]["_path"] if arm in records else None,
            "stopped_early": records[arm]["stopped_early"] if arm in records else None,
            "cells": n,
            "parseable_cells": n_parse,
            "own_match_rate": round(own / n_parse, 4) if n_parse else None,
            "other_match_rate": round(other / n_parse, 4) if n_parse else None,
            "own_match_count": own,
            "other_match_count": other,
            "truncation_invalid_cells": trunc_invalid,
            "truncation_invalid_rate": round(trunc_invalid / n, 4) if n else None,
            "truncated_done_reason_cells": trunc_any,
            "primary_count": primary,
            "contract_compliance_rate": round(contract_ok / n, 4) if n else None,
            "failure_modes": modes,
            "failure_mode_total": sum(modes.values()),
            "failure_flags": flags,
            "total_failure_events": sum(flags.values()),
            "failed_cells": sum(1 for r in arm_rows if r["failure_flags"]),
        }

    g1_ok = all(
        arm_stats[a]["parseable_cells"] > 0
        and arm_stats[a]["own_match_rate"] >= 0.9
        and arm_stats[a]["other_match_rate"] <= 0.1
        for a in ARMS
    )
    g2_ok = all(
        arm_stats[a]["cells"] > 0
        and arm_stats[a]["truncation_invalid_rate"] <= 0.20
        for a in ARMS
    )
    complete = all(
        arm_stats[a]["cells"] == len(TASKS) and not arm_stats[a]["stopped_early"]
        for a in ARMS
    )

    flags_first = [rows["answer_first"][t.id]["primary_correct"] for t in TASKS]
    flags_second = [rows["derivation_first"][t.id]["primary_correct"] for t in TASKS]
    b = sum(1 for x, y in zip(flags_first, flags_second) if x and not y)
    c = sum(1 for x, y in zip(flags_first, flags_second) if not x and y)
    paired = {
        "tasks": len(TASKS),
        "answer_first_primary_count": sum(flags_first),
        "derivation_first_primary_count": sum(flags_second),
        "difference": sum(flags_second) - sum(flags_first),
        "risk_difference": round(
            (sum(flags_second) - sum(flags_first)) / len(TASKS), 4
        ),
        "risk_difference_ci95": _bootstrap_risk_difference(flags_first, flags_second),
        "discordant_answer_only": b,
        "discordant_derivation_only": c,
        "mcnemar_exact_two_sided_p": round(_mcnemar_exact(b, c), 6),
    }
    success = bool(
        g1_ok
        and g2_ok
        and complete
        and paired["difference"] > 0
        and arm_stats["derivation_first"]["total_failure_events"]
        <= arm_stats["answer_first"]["total_failure_events"]
    )
    return {
        "gates": {
            "G1_manipulation_pass": g1_ok,
            "G1_verdict": "PASS" if g1_ok else "INVALID MANIPULATION",
            "G2_length_pass": g2_ok,
            "G2_verdict": "PASS" if g2_ok else "LENGTH-CONFOUNDED",
        },
        "complete": complete,
        "arms": arm_stats,
        "paired": paired,
        "success_criterion_met": success,
        "protected_manifest": verify_protected(),
        "artifact_sha256": {
            name: _sha256_file(DATA_DIR / name)
            for name in sorted(
                {r["_path"] for r in records.values()}
                | {STORE_DB_NAME, STORE_JSONL_NAME}
            )
        },
        # Canonical module hash is the Git blob hash (line-ending invariant).
        "module_sha256": module_git_blob_sha256(),
        "module_worktree_sha256": _sha256_file(Path(__file__)),
    }


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(
        description="Order-v2 study: final_answer position (local Ollama only)"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="print frozen manifest, task and protected-hash snapshot; no calls",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify FROZEN byte-identity and report LIVE before/after; no calls",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="run both arms sequentially; one call per task per arm",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="read results and apply pre-registered analysis; no calls",
    )
    args = parser.parse_args(argv)

    if args.manifest:
        snapshot = manifest_snapshot()
        snapshot["frozen_verification"] = verify_protected()
        snapshot["frozen_tasks_verification"] = _verify_frozen()
        snapshot["copy_checks"] = _assert_no_copy()
        snapshot["tasks"] = [t.metadata() for t in TASKS]
        snapshot["ground_truth"] = ground_truth_manifest()
        print(json.dumps(snapshot, ensure_ascii=True, indent=2))
        return 0
    if args.verify:
        print(json.dumps(verify_protected(), ensure_ascii=True, indent=2))
        return 0
    if args.run:
        run_study()
        return 0
    if args.summarize:
        result = summarize()
        out = DATA_DIR / SUMMARY_NAME
        out.write_text(
            json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
