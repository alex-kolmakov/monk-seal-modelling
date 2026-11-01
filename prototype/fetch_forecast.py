"""Download the latest Copernicus IBI forecast (hourly waves and sea surface height) for the Desertas box.

Credentials come from COPERNICUS_USERNAME / COPERNICUS_PASSWORD (repo .env). Writes
data/forecast/waves_anfc.nc and data/forecast/zos_anfc.nc; run build_forecast.py afterwards.
"""
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import copernicusmarine as cm

OUT = Path(__file__).parent.parent / "data" / "forecast"
OUT.mkdir(parents=True, exist_ok=True)
now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
BOX = dict(minimum_longitude=-17.5, maximum_longitude=-16.03, minimum_latitude=32.2, maximum_latitude=33.5,
           start_datetime=now.strftime("%Y-%m-%dT%H:%M:%S"), end_datetime=(now + timedelta(days=11)).strftime("%Y-%m-%dT%H:%M:%S"))
AUTH = dict(username=os.environ["COPERNICUS_USERNAME"], password=os.environ["COPERNICUS_PASSWORD"])

for ds, variables, name in (
    ("cmems_mod_ibi_wav_anfc_0.027deg_PT1H-i", ["VHM0", "VMDR", "VHM0_SW1", "VMDR_SW1"], "waves_anfc.nc"),
    ("cmems_mod_ibi_phy_anfc_0.027deg-2D_PT1H-m", ["zos"], "zos_anfc.nc"),
):
    cm.subset(dataset_id=ds, variables=variables, output_directory=str(OUT), output_filename=name, overwrite=True, **AUTH, **BOX)
