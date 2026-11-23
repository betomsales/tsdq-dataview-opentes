from io import BytesIO
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import pandas as pd

from components.analise_eletrica_rede import montar_estrutura_analise_rede
from components.entrada_zip import cached_zip_results
from modules.network.cosim_loader import apply_measurement_snapshot
from modules.network.d3_renderer import build_d3_temporal_frames
from modules.network.dss_loader import extract_zip
from modules.network.dss_results import _channel_quantities, load_dss_zip, select_branch_terminals
from modules.network.equipment_view import connected_equipment, equipment_measurements


def archive(script, filename="Master.dss", extra=None):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr(filename, script)
        for name, value in (extra or {}).items():
            zipped.writestr(name, value)
    return buffer.getvalue()


SCRIPT = """
Clear
New Circuit.test bus1=sourcebus basekv=12.47 pu=1.01
New Transformer.tx phases=3 windings=2 buses=[sourcebus,b] conns=[wye,wye] kvs=[12.47,0.48] kvas=[500,500] xhl=2
New Line.feed phases=3 bus1=b bus2=c r1=0.01 x1=0.01 length=0.1
New Load.single phases=1 bus1=c.3.0 kv=0.277128 kw=20 pf=0.95
New PVSystem.pv-alpha phases=3 bus1=b kv=0.48 kva=50 pmpp=30 irradiance=1
New Monitor.high element=Transformer.tx terminal=1 mode=0
New Monitor.low element=Transformer.tx terminal=2 mode=0
New Monitor.phigh element=Transformer.tx terminal=1 mode=1 ppolar=no
New Monitor.plow element=Transformer.tx terminal=2 mode=1 ppolar=no
New Monitor.loadvi element=Load.single terminal=1 mode=0 vipolar=no
New Monitor.loadpq element=Load.single terminal=1 mode=1 ppolar=no
New Monitor.pvpq element=PVSystem.pv-alpha terminal=1 mode=1 ppolar=yes
Set voltagebases=[12.47,0.48]
Calcvoltagebases
Set mode=daily number=3 stepsize=1h
Solve
"""


class DSSMonitorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = archive(SCRIPT)
        cls.result = load_dss_zip(cls.content)

    def test_samples_and_units_come_from_engine_not_embedded_csv(self):
        result = load_dss_zip(archive(SCRIPT, extra={"old.csv": "hour,P1\n1,999999999\n"}))
        self.assertEqual(result.dataframe["Tempo (h)"].tolist(), [1, 2, 3])
        self.assertEqual(len(result.monitors), 7)
        self.assertTrue(all(row["Amostras"] == 3 for row in result.monitors))
        structure = montar_estrutura_analise_rede(result.graph, select_branch_terminals(result.catalog, {}))
        variables = [v for group in structure.values() for values in group.values() for v in values]
        self.assertIn("kW", {v["unidade_detectada"] for v in variables})
        self.assertIn("kVar", {v["unidade_detectada"] for v in variables})
        self.assertIn("pu", {v["unidade_detectada"] for v in variables})
        self.assertIn("A", {v["unidade_detectada"] for v in variables})

    def test_voltage_base_and_original_volts_are_both_traceable(self):
        result = self.result
        for bus, monitor in (("sourcebus", "high"), ("b", "low")):
            base = result.graph.nodes[bus].metadata["kv_base"]
            raw = result.raw[f"{monitor} | 1: V1"]
            pd.testing.assert_series_equal(result.dataframe[f"DSS-zip.Bus-{bus}-V1_pu"], raw / (1000 * base), check_names=False)

    def test_conductor_three_maps_to_phase_c_and_neutral_is_not_a_phase(self):
        catalog = self.result.catalog
        load_items = [item for item in catalog if item["entity_name"] == "single" and item["target_kind"] == "equipment"]
        self.assertTrue(load_items)
        self.assertTrue(all(item["variable"].startswith(("P3_", "Q3_", "I3_")) for item in load_items))
        c_voltages = [item for item in catalog if item["target_kind"] == "node" and item["target_id"] == "c"]
        self.assertEqual({item["variable"] for item in c_voltages}, {"V3_pu", "V3_ang"})
        self.assertIn("loadpq | 3: P2 (kW)", self.result.raw.columns)

    def test_transformer_terminals_are_filtered_before_existing_calculations(self):
        result = self.result
        for terminal in (1, 2):
            catalog = select_branch_terminals(result.catalog, {"transformer_tx": terminal})
            edge_items = [item for item in catalog if item["target_kind"] == "edge"]
            self.assertEqual({item["terminal"] for item in edge_items}, {terminal})
            self.assertEqual(len(edge_items), 12)
        self.assertEqual({item["terminal"] for item in select_branch_terminals(result.catalog, {}) if item["target_kind"] == "edge"}, {1})

    def test_snapshot_equipment_identity_and_d3_frames_use_shared_pipeline(self):
        result = load_dss_zip(self.content)
        catalog = select_branch_terminals(result.catalog, {})
        stats = apply_measurement_snapshot(result.graph, result.dataframe, catalog, 0)
        self.assertEqual(stats["unassociated_columns"], 0)
        equipment = connected_equipment(result.graph)
        load = next(e for e in equipment.values() if e.kind == "Load")
        pv = next(e for e in equipment.values() if e.kind == "PVSystem")
        self.assertTrue(all(m["entity_name"] == "single" for m in equipment_measurements(result.graph, load)))
        self.assertTrue(all(m["entity_name"] == "pv-alpha" for m in equipment_measurements(result.graph, pv)))
        frames = build_d3_temporal_frames(result.graph, result.dataframe, catalog, result.dataframe["Tempo (h)"])
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0]["label"], "1.0 h")

    def test_pv_sign_is_normalized_for_injection_with_raw_channels_unchanged(self):
        item = next(i for i in self.result.catalog if i["target_kind"] == "pv" and i["variable"] == "P1_kw")
        self.assertGreater(self.result.dataframe[item["column"]].iloc[0], 0)
        self.assertGreater(self.result.raw["pvpq | 1: S1 (kVA)"].iloc[0], 0)

    def test_complex_channels_and_zero_are_decoded_without_unit_guessing(self):
        output, unused = _channel_quantities(["V1.re", "V1.im", "I1", "IAngle1"],
                                           [np.array([0., 3.]), np.array([0., 4.]), np.array([0., 2.]), np.array([0., -90.])], 0)
        self.assertFalse(unused)
        np.testing.assert_array_equal(output[0][2], [0, 5])
        self.assertAlmostEqual(output[1][2][1], 53.13010235415598)
        self.assertEqual(output[2][3], "A")
        polar, _ = _channel_quantities(["S1 (kVA)", "Ang1"], [np.array([10.]), np.array([60.])], 1)
        self.assertAlmostEqual(polar[0][2][0], 5)
        self.assertAlmostEqual(polar[1][2][0], 8.660254037844386)

    def test_modes_without_supported_series_remain_raw_and_do_not_abort_graph(self):
        script = SCRIPT.replace("New Monitor.pvpq", "New Monitor.tap element=Transformer.tx mode=2\nNew Monitor.pvpq")
        result = load_dss_zip(archive(script))
        self.assertTrue(any("tap" in warning for warning in result.warnings))
        self.assertTrue(any(column.startswith("tap |") for column in result.raw.columns))
        self.assertFalse(result.dataframe.empty)

    def test_no_solve_no_monitors_and_single_sample_are_handled(self):
        without = load_dss_zip(archive(SCRIPT.split("Set mode=daily")[0]))
        self.assertTrue(without.dataframe.empty)
        self.assertGreater(without.graph.total_nodes, 0)
        one = load_dss_zip(archive(SCRIPT.replace("number=3", "number=1")))
        self.assertEqual(len(one.dataframe), 1)
        none = load_dss_zip(archive("New Circuit.only bus1=a basekv=12.47"))
        self.assertTrue(none.dataframe.empty)

    def test_uppercase_dss_and_isolated_context_leave_cwd_unchanged(self):
        cwd = os.getcwd()
        other = load_dss_zip(archive("New Circuit.other bus1=isolated", filename="MASTER.DSS"))
        self.assertEqual(os.getcwd(), cwd)
        self.assertEqual(set(other.graph.nodes), {"isolated"})
        self.assertIn("sourcebus", self.result.graph.nodes)

    def test_zip_cannot_extract_outside_temporary_root(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                extract_zip(BytesIO(archive("x", filename="../outside.dss")), root)
            self.assertFalse((Path(root).parent / "outside.dss").exists())

    def test_ui_cache_reuses_data_not_live_engine(self):
        cached_zip_results.clear()
        with patch("components.entrada_zip.load_dss_zip", return_value=copy.deepcopy(self.result)) as load:
            a = cached_zip_results(b"cache-test-a")
            b = cached_zip_results(b"cache-test-a")
            self.assertEqual(load.call_count, 1)
            self.assertIsNot(a.graph, b.graph)
            a.graph.nodes.clear()
            self.assertTrue(b.graph.nodes)
        cached_zip_results.clear()


if __name__ == "__main__":
    unittest.main()
