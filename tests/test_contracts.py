"""Data contracts: a re-issued or changed survey file is refused, with every difference named."""
import pytest

from ingestion import contracts
from ingestion.contracts import ContractViolation

ORIGINAL = "RandomID,POSTWT,agency,Q1,DLEAVING\n1,1.5,XX,4,A\n2,2.0,XX,X,B\n3,0.9,XX,,C\n"


@pytest.fixture
def wave(tmp_path, monkeypatch):
    """A one-wave world: a data file, and a contract drafted from it."""
    (tmp_path / "data" / "2030").mkdir(parents=True)
    (tmp_path / "contracts").mkdir()
    monkeypatch.setattr(contracts, "EXTRACTED", tmp_path / "data")
    monkeypatch.setattr(contracts, "CONTRACTS", tmp_path / "contracts")
    csv_path = tmp_path / "data" / "2030" / "fevs_2030.csv"
    csv_path.write_text(ORIGINAL)
    contracts.path_for(2030).write_text(contracts._dump(contracts.draft(2030)))
    return csv_path


def test_an_unchanged_file_passes_its_contract(wave):
    assert contracts.check(2030)["row_count"] == 3


def test_the_contract_records_each_items_observed_answers(wave):
    q1 = next(c for c in contracts.draft(2030)["columns"] if c["name"] == "Q1")
    assert q1 == {"name": "Q1", "role": "item", "allowed": ["4", "X"]}


def test_a_new_column_is_refused(wave):
    wave.write_text(ORIGINAL.replace("DLEAVING\n", "DLEAVING,DNEW\n").replace("A\n", "A,1\n")
                    .replace("B\n", "B,1\n").replace("C\n", "C,1\n"))
    with pytest.raises(ContractViolation, match="column added: DNEW"):
        contracts.check(2030)


def test_a_dropped_column_is_refused(wave):
    wave.write_text("RandomID,POSTWT,agency,Q1\n1,1.5,XX,4\n2,2.0,XX,X\n3,0.9,XX,\n")
    with pytest.raises(ContractViolation, match="column removed: DLEAVING"):
        contracts.check(2030)


def test_a_new_answer_code_is_refused_by_name(wave):
    wave.write_text(ORIGINAL.replace(",4,A", ",9,A"))
    with pytest.raises(ContractViolation, match=r"Q1: values not in contract: \['9'\]"):
        contracts.check(2030)


def test_a_re_issued_file_with_extra_rows_is_refused(wave):
    wave.write_text(ORIGINAL + "4,1.1,XX,4,D\n")
    with pytest.raises(ContractViolation, match="row count changed: 3 -> 4"):
        contracts.check(2030)
