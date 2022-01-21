import mock
import pandas as pd

from flytekit import StructuredDataset, task, workflow

try:
    from typing import Annotated, Any
except ImportError:
    from typing_extensions import Annotated


@task
def t1(df: pd.DataFrame) -> StructuredDataset:
    return StructuredDataset(dataframe=df, uri="bq://project:flyte.table")


@task
def t2(sd: StructuredDataset) -> pd.DataFrame:
    return sd.open(pd.DataFrame).all()


@workflow
def wf(df: pd.DataFrame) -> pd.DataFrame:
    sd = t1(df=df)
    return t2(sd=sd)


@mock.patch("google.cloud.bigquery.Client")
@mock.patch("google.cloud.bigquery_storage.BigQueryReadClient")
@mock.patch("google.cloud.bigquery_storage_v1.reader.ReadRowsStream")
def test_bq_wf(mock_read_rows_stream, mock_bigquery_read_client, mock_client):
    class mock_pages:
        def to_dataframe(self):
            return pd.DataFrame({"Name": ["Tom", "Joseph"], "Age": [20, 22]})

    class mock_rows:
        pages = [mock_pages()]

    mock_client.load_table_from_dataframe.return_value = None
    mock_read_rows_stream.rows.return_value = mock_rows
    mock_bigquery_read_client.read_rows.return_value = mock_read_rows_stream
    mock_bigquery_read_client.return_value = mock_bigquery_read_client

    df = pd.DataFrame({"Name": ["Tom", "Joseph"], "Age": [20, 22]})
    assert wf(df=df).equals(df)