import pytest
from mock import patch
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from string import ascii_lowercase
import random
from dfmock import DFMock
import s3parq.publish_parq as parq
import s3fs
from moto import mock_s3


@mock_s3
class Test:

    def setup_s3(self):
        def rand_string():
            return ''.join([random.choice(ascii_lowercase) for x in range(0, 10)])

        bucket = rand_string()
        key = rand_string()

        s3_client = boto3.client('s3')
        s3_client.create_bucket(Bucket=bucket)

        return bucket, key

    def setup_df(self):
        df = DFMock(count=100)
        df.columns = {"grouped_col": {"option_count": 4, "option_type": "string"},
                      "text_col": "string",
                      "int_col": "integer",
                      "float_col": "float"}
        df.generate_dataframe()
        df.dataframe

        return tuple(df.columns.keys()), df.dataframe

    def test_works_without_partitions(self):
        columns, dataframe = self.setup_df()
        bucket, key = self.setup_s3()
        partitions = []
        parq.publish(bucket=bucket, key=key,
                     dataframe=dataframe, partitions=partitions)

    def test_accepts_valid_partitions(self):
        columns, dataframe = self.setup_df()
        parq.check_partitions(columns, dataframe)

    def test_reject_non_column_partitions(self):
        columns, dataframe = self.setup_df()
        with pytest.raises(ValueError):
            parq.check_partitions(('banana',), dataframe)

    def test_reject_timedelta_dataframes(self):
        columns, dataframe = self.setup_df()
        bucket, key = self.setup_s3()
        partitions = ['text_col']
        dataframe['time_col'] = pd.Timedelta('1 days')
        with pytest.raises(NotImplementedError):
            parq.publish(bucket=bucket, key=key,
                         dataframe=dataframe, partitions=partitions)

    def test_reject_protected_name_partitions(self):
        assert parq._check_partition_compatibility("shoe")
        assert parq._check_partition_compatibility("all") is False

    def test_generates_partitions_in_order(self):
        columns, dataframe = self.setup_df()
        bucket, key = self.setup_s3()
        partitions = columns[:1]
        with patch('s3parq.publish_parq.boto3', return_value=True) as mock_boto3:
            with patch('s3parq.publish_parq.pq.write_to_dataset', return_value=None) as mock_method:
                parq._gen_parquet_to_s3(bucket, key, dataframe, partitions)
                arg, kwarg = mock_method.call_args
                assert kwarg['partition_cols'] == partitions

    def test_input_equals_output(self):
        columns, dataframe = self.setup_df()
        bucket, key = self.setup_s3()
        s3_path = f"s3://{bucket}/{key}"
        partitions = [columns[0]]
        parq.publish(bucket=bucket, key=key,
                     dataframe=dataframe, partitions=partitions)

        from_s3 = pq.ParquetDataset(s3_path, filesystem=s3fs.S3FileSystem())
        s3pd = from_s3.read().to_pandas()
        pre_df = dataframe

        assert set(zip(s3pd.int_col, s3pd.float_col, s3pd.text_col, s3pd.grouped_col)) - \
            set(zip(dataframe.int_col, dataframe.float_col,
                    dataframe.text_col, dataframe.grouped_col)) == set()

    def test_reject_empty_dataframe(self):
        dataframe = pd.DataFrame()
        bucket, key = self.setup_s3()
        s3_path = f"s3://{bucket}/{key}"

        with pytest.raises(ValueError):
            parq.publish(bucket=bucket, key=key,
                        dataframe=dataframe, partitions=[])

    def test_set_metadata_correctly(self):
        columns, dataframe = self.setup_df()
        bucket, key = self.setup_s3()
        s3_client = boto3.client('s3')
        partitions = ['grouped_col']
        parq.publish(bucket=bucket, key=key,
                     dataframe=dataframe, partitions=partitions)
        for obj in s3_client.list_objects(Bucket=bucket)['Contents']:
            if obj['Key'].endswith(".parquet"):
                meta = s3_client.get_object(
                    Bucket=bucket, Key=obj['Key'])['Metadata']
                assert meta['partition_data_types'] == str(
                    {"grouped_col": "string"})
    '''


    ## timedeltas no good
    def test_timedeltas_rejected(self):
        bucket = MockHelper().random_name()
        key = MockHelper().random_name()

        s3_client = boto3.client('s3')
        s3_client.create_bucket(Bucket=bucket)

        df = DFMock(count=100)
        df.columns = {"timedelta_col": "timedelta", "int_col": "int", "float_col": "float",
                      "bool_col": "boolean", "grouped_col": {"option_count": 4, "option_type": "string"}}
        df.generate_dataframe()

        with pytest.raises(NotImplementedError):
            parq = pub_parq.S3PublishParq(
                dataframe=df.dataframe, bucket=bucket, key=key, partitions=['grouped_col'])
'''
