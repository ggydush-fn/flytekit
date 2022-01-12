import os
import typing
from typing import TypeVar

import pandas
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from flytekit import FlyteContext
from flytekit.core.data_persistence import DataPersistencePlugins
from flytekit.models import literals
from flytekit.models.literals import StructuredDatasetMetadata
from flytekit.models.types import StructuredDatasetType
from flytekit.types.structured.structured_dataset import (
    FLYTE_DATASET_TRANSFORMER,
    LOCAL,
    PARQUET,
    S3,
    StructuredDataset,
    StructuredDatasetDecoder,
    StructuredDatasetEncoder,
)
from flytekit.types.structured.utils import get_filesystem

T = TypeVar("T")


class PandasToParquetEncodingHandler(StructuredDatasetEncoder):
    def __init__(self, protocol: str):
        super().__init__(pd.DataFrame, protocol, PARQUET)
        # todo: Use this somehow instead of relaying ont he ctx file_access
        self._persistence = DataPersistencePlugins.find_plugin(protocol)()

    def encode(
        self,
        ctx: FlyteContext,
        structured_dataset: StructuredDataset,
        structured_dataset_type: StructuredDatasetType,
    ) -> literals.StructuredDataset:

        path = typing.cast(str, structured_dataset.uri) or ctx.file_access.get_random_remote_directory()
        df = typing.cast(pd.DataFrame, structured_dataset.dataframe)
        local_dir = ctx.file_access.get_random_local_directory()
        local_path = os.path.join(local_dir, f"{0:05}")
        df.to_parquet(local_path, coerce_timestamps="us", allow_truncated_timestamps=False)
        ctx.file_access.upload_directory(local_dir, path)
        structured_dataset_type.format = PARQUET
        return literals.StructuredDataset(uri=path, metadata=StructuredDatasetMetadata(structured_dataset_type))


class ParquetToPandasDecodingHandler(StructuredDatasetDecoder):
    def __init__(self, protocol: str):
        super().__init__(pd.DataFrame, protocol, PARQUET)

    def decode(
        self,
        ctx: FlyteContext,
        flyte_value: literals.StructuredDataset,
    ) -> pd.DataFrame:
        path = flyte_value.uri
        local_dir = ctx.file_access.get_random_local_directory()
        ctx.file_access.get_data(path, local_dir, is_multipart=True)
        return pd.read_parquet(local_dir)


class ArrowToParquetEncodingHandler(StructuredDatasetEncoder):
    def __init__(self, protocol: str):
        super().__init__(pa.Table, protocol, PARQUET)

    def encode(
        self,
        ctx: FlyteContext,
        structured_dataset: StructuredDataset,
        structured_dataset_type: StructuredDatasetType,
    ) -> literals.StructuredDataset:
        path = typing.cast(str, structured_dataset.uri) or ctx.file_access.get_random_remote_path()
        df = structured_dataset.dataframe
        pq.write_table(df, path, filesystem=get_filesystem(path))
        return literals.StructuredDataset(uri=path, metadata=StructuredDatasetMetadata(structured_dataset_type))


class ParquetToArrowDecodingHandler(StructuredDatasetDecoder):
    def __init__(self, protocol: str):
        super().__init__(pa.Table, protocol, PARQUET)

    def decode(
        self,
        ctx: FlyteContext,
        flyte_value: literals.StructuredDataset,
    ) -> pa.Table:
        path = flyte_value.uri
        return pq.read_table(path, filesystem=get_filesystem(path))


for protocol in [LOCAL, S3]:  # Should we add GCS
    FLYTE_DATASET_TRANSFORMER.register_handler(PandasToParquetEncodingHandler(protocol), default_for_type=True)
    FLYTE_DATASET_TRANSFORMER.register_handler(ParquetToPandasDecodingHandler(protocol), default_for_type=True)
    FLYTE_DATASET_TRANSFORMER.register_handler(ArrowToParquetEncodingHandler(protocol), default_for_type=True)
    FLYTE_DATASET_TRANSFORMER.register_handler(ParquetToArrowDecodingHandler(protocol), default_for_type=True)