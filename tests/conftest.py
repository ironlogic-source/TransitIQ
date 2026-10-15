import pytest
from functools import partial

from backend.constraints import PlanContext
from tests import toy_data as T
from tests.mock_sim import run_simulation


@pytest.fixture
def ctx():
    return PlanContext(T.VEHICLES, T.ROUTES, T.STOPS, T.SCHEDULES, scenario={}, params=T.PARAMS)


@pytest.fixture
def ctx_disrupted():
    return PlanContext(T.VEHICLES, T.ROUTES, T.STOPS, T.SCHEDULES, scenario=T.DISRUPTION, params=T.PARAMS)


@pytest.fixture
def sched():
    return T.SCHEDULES.copy()


@pytest.fixture
def run_sim_disrupted():
    return partial(run_simulation, vehicles=T.VEHICLES, demand=T.DEMAND, routes=T.ROUTES, scenario=T.DISRUPTION)
