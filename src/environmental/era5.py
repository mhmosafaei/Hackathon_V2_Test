"""Historical ERA5 weather only; unsupported ERA5 waves remain explicit gaps."""
from .ecmwf import retrieve as weather


def retrieve(request):
    return weather(request, historical=True)
