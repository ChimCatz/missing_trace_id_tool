from __future__ import annotations

from typing import Callable

import pandas as pd

from zoho_client import ZohoClient, load_config

StatusCallback = Callable[[str], None]

LEAD_TRACE_LOOKUP_FIELDS = [
    "id",
    "Trace_ID",
    "First_Name",
    "Last_Name",
    "Company",
    "Primary_Email",
    "Modified_Time",
]

COMPANY_REGISTRY_LOOKUP_FIELDS = [
    "id",
    "Company_ID",
    "Name",
    "Website",
    "HQ_Location",
    "HQ_Country_Code",
    "Modified_Time",
]


def fetch_trace_id_lookup_dataframe(
    status_callback: StatusCallback | None = None,
) -> pd.DataFrame:
    config = load_config()
    with ZohoClient(config) as client:
        dataframe = client.fetch_module_dataframe(
            config.leads_module,
            LEAD_TRACE_LOOKUP_FIELDS,
            status_callback=status_callback,
        )

    dataframe = dataframe.copy().rename(
        columns={
            "Trace_ID": "Trace ID",
            "id": "Record Id",
            "Primary_Email": "Primary Email",
            "Modified_Time": "Modified Time",
        }
    )

    if {"First_Name", "Last_Name"}.intersection(dataframe.columns):
        dataframe["Lead Name"] = (
            dataframe.get("First_Name", "").astype(str).str.strip()
            + " "
            + dataframe.get("Last_Name", "").astype(str).str.strip()
        ).str.strip()

    ordered_columns = [
        column_name
        for column_name in [
            "Record Id",
            "Trace ID",
            "Lead Name",
            "Company",
            "Primary Email",
            "Modified Time",
        ]
        if column_name in dataframe.columns
    ]
    return dataframe.loc[:, ordered_columns].copy()


def fetch_company_id_lookup_dataframe(
    status_callback: StatusCallback | None = None,
) -> pd.DataFrame:
    config = load_config()
    with ZohoClient(config) as client:
        dataframe = client.fetch_module_dataframe(
            config.company_registry_module,
            COMPANY_REGISTRY_LOOKUP_FIELDS,
            status_callback=status_callback,
        )

    dataframe = dataframe.copy().rename(
        columns={
            "id": "Record Id",
            "Name": "Company Name",
            "Website": "Website",
            "HQ_Location": "HQ Location",
            "HQ_Country_Code": "HQ Country Code",
            "Modified_Time": "Modified Time",
            "Company_ID": "Company ID",
        }
    )

    ordered_columns = [
        column_name
        for column_name in [
            "Record Id",
            "Company ID",
            "Company Name",
            "Website",
            "HQ Location",
            "HQ Country Code",
            "Modified Time",
        ]
        if column_name in dataframe.columns
    ]
    return dataframe.loc[:, ordered_columns].copy()
