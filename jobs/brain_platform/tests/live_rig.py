"""Platform-test flavour of the shared rig: clock one hour after the synthetic fixtures' T0."""
import datetime as dt

from publisher_fixtures import T0
from sector_brain_platform.publisher_live.rig import Rig as _Rig


class Rig(_Rig):
    def __init__(self, *a, **kw):
        kw.setdefault("clock", T0 + dt.timedelta(hours=1))
        super().__init__(*a, **kw)
