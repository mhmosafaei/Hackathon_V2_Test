"""Configured TUR adapter tests use local xarray fixtures only."""
import numpy as np
import xarray as xr
import pytest
from src.environmental import copernicus
from src.environmental.errors import ProviderError
from tests.test_copernicus_current_oxygen_patch import mock_client,request


def dataset(unit='FNU'):
    ds=xr.Dataset({'TUR':(('time','latitude','longitude'),np.array([[[26.]]]))},
        coords={'time':np.array(['2026-10-14'],dtype='datetime64[D]'),'latitude':[54.],'longitude':[-6.]})
    ds.TUR.attrs['units']=unit
    return ds


def test_observation_compatible_fnu_source_opens_and_preserves_provenance(monkeypatch):
    calls=mock_client(monkeypatch,dataset())
    evidence=copernicus.worker(request('turbidity',requested_unit='FNU'))
    assert len(calls)==1 and calls[0]['variables']==['TUR']
    assert evidence['dataset_id']=='cmems_obs_oc_nws_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m'
    assert evidence['dataset_name']=='OCEANCOLOUR_NWS_BGC_HR_L3_NRT_009_203'
    assert evidence['data_type']=='SATELLITE_OBSERVATION'
    assert evidence['points'][0]['unit']=='FNU' and evidence['points'][0]['raw_value']==26
    assert evidence['latitude']==54 and evidence['longitude']==-6
    assert evidence['distance_km']==0


@pytest.mark.parametrize('unit',['NTU','mg/L',''])
def test_incompatible_native_units_fail_closed(monkeypatch,unit):
    mock_client(monkeypatch,dataset(unit))
    with pytest.raises(ProviderError) as exc:copernicus.worker(request('turbidity',requested_unit='FNU'))
    assert exc.value.category=='UNIT_INCOMPATIBLE'


def test_model_requirement_cannot_use_observation_mapping(monkeypatch):
    calls=mock_client(monkeypatch,dataset())
    req=request('turbidity',requested_unit='FNU')
    req.requirement_text='Turbidity shall be assessed in FNU using compatible Copernicus Marine modelled turbidity evidence.'
    with pytest.raises(ProviderError) as exc:copernicus.worker(req)
    assert exc.value.category=='NO_COMPATIBLE_CONFIGURED_SOURCE'
    assert not calls


def test_invalid_dataset_is_explicit_not_generic(monkeypatch):
    class Client:
        def open_dataset(self,**kwargs):raise ValueError('dataset_id not found')
    monkeypatch.setattr(copernicus,'_load_worker_dependencies',lambda:(np,Client()))
    with pytest.raises(ProviderError) as exc:copernicus.worker(request('turbidity',requested_unit='FNU'))
    assert exc.value.category=='CONFIGURED_DATASET_UNAVAILABLE'


def test_tur_observation_outside_native_time_bounds_is_explicit(monkeypatch):
    class CoordinatesOutOfDatasetBounds(Exception):
        pass
    calls=[]
    class Client:
        def open_dataset(self, **kwargs):
            calls.append(kwargs)
            raise CoordinatesOutOfDatasetBounds('Subset for the time dimension exceeds dataset coordinates; secret must not escape')
    monkeypatch.setattr(copernicus,'_load_worker_dependencies',lambda:(np,Client()))
    with pytest.raises(ProviderError) as exc:
        copernicus.worker(request('turbidity',requested_unit='FNU'))
    assert len(calls)==1
    assert exc.value.category=='NO_COMPATIBLE_ACCESSIBLE_SOURCE'
    assert exc.value.metadata['failure_stage']=='TEMPORAL_SELECTION'
    assert exc.value.metadata['evidence_mode']=='OBSERVATION'
    assert exc.value.metadata['dataset_variable']=='TUR'
    assert 'secret' not in exc.value.safe_message
    assert 'no fallback' in exc.value.safe_message.lower()


def test_other_tur_open_failures_are_not_misclassified_as_time_bounds(monkeypatch):
    class Client:
        def open_dataset(self, **kwargs):
            raise RuntimeError('unclassified server failure')
    monkeypatch.setattr(copernicus,'_load_worker_dependencies',lambda:(np,Client()))
    with pytest.raises(ProviderError) as exc:
        copernicus.worker(request('turbidity',requested_unit='FNU'))
    assert exc.value.category=='DATASET_OPEN'


def test_masked_newest_observation_searches_older_native_grid(monkeypatch):
    ds=xr.Dataset({'TUR':(('time','latitude','longitude'),np.array([[[24.]],[[np.nan]]]))},
        coords={'time':np.array(['2026-10-13','2026-10-14'],dtype='datetime64[D]'),
                'latitude':[54.],'longitude':[-6.]})
    ds.TUR.attrs['units']='FNU'
    calls=mock_client(monkeypatch,ds)
    result=copernicus.worker(request('turbidity',requested_unit='FNU'))
    assert len(calls)==1
    assert result['points'][0]['raw_value']==24
    assert result['points'][0]['data_time']=='2026-10-13T00:00:00+00:00'
    assert result['data_type']=='SATELLITE_OBSERVATION'
