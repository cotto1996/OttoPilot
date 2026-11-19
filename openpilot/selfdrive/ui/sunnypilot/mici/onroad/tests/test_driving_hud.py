import unittest
from dataclasses import replace
from types import SimpleNamespace

import pyray as rl

from openpilot.selfdrive.ui.sunnypilot.mici.onroad.control_colors import WHITE, DrivingHudSettings, acceleration_wheel_color
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.lead_stats import UNAVAILABLE, LeadStats, lead_readings


STARTED_FRAME = 10


class DrivingMessages(dict):
  def __init__(self):
    super().__init__(
      carControl=SimpleNamespace(enabled=True, latActive=True, longActive=True),
      carState=SimpleNamespace(steeringPressed=False, vEgo=20.0),
      onroadEvents=[],
      radarState=SimpleNamespace(leadOne=SimpleNamespace(present=True, dRel=30.0, vLead=20.0)),
      selfdriveStateSP=SimpleNamespace(mads=SimpleNamespace(available=True, enabled=True, state="enabled")),
    )
    self.alive = dict.fromkeys(self, True)
    self.valid = dict.fromkeys(self, True)
    self.recv_frame = dict.fromkeys(self, STARTED_FRAME)


class TestDrivingHud(unittest.TestCase):
  def test_lead_card_uses_the_camera_viewport(self):
    for width, height in ((476, 72), (275, 58)):
      with self.subTest(width=width):
        card = LeadStats.card_bounds(rl.Rectangle(25, 5, width, 240))
        assert card is not None
        assert (card.x, card.width, card.height, card.y + card.height) == (37, width - 24, height, 231)
    assert LeadStats.card_bounds(rl.Rectangle(0, 0, 100, 240)) is None

  def test_wheel_color_follows_measured_acceleration(self):
    sm = DrivingMessages()
    for acceleration, color in ((0.5, (67, 224, 135)), (-0.5, (245, 70, 70)), (0.05, WHITE), (float("inf"), WHITE)):
      with self.subTest(acceleration=acceleration):
        sm["carState"].aEgo = acceleration
        assert acceleration_wheel_color(sm, STARTED_FRAME) == color
    sm["carState"].aEgo = 0.5
    sm.recv_frame["carState"] = STARTED_FRAME - 1
    assert acceleration_wheel_color(sm, STARTED_FRAME) == WHITE

  def test_colors_follow_active_axes(self):
    cases = [
      (True, True, (32, 216, 117)),
      (True, False, (38, 143, 255)),
      (False, True, (244, 74, 184)),
      (False, False, None),
    ]
    for lateral, longitudinal, color in cases:
      with self.subTest(lateral=lateral, longitudinal=longitudinal):
        sm = DrivingMessages()
        sm["carControl"].latActive = lateral
        sm["carControl"].longActive = longitudinal
        assert DrivingHudSettings().state_color(sm, STARTED_FRAME, True) == color

  def test_driver_steering_override_requires_active_lateral_or_mads_override(self):
    settings = DrivingHudSettings()
    sm = DrivingMessages()
    sm["carState"].steeringPressed = True
    assert settings.state_color(sm, STARTED_FRAME, True) == (146, 153, 163)

    sm["carControl"].latActive = False
    sm["selfdriveStateSP"].mads.state = "paused"
    assert settings.state_color(sm, STARTED_FRAME, True) == (244, 74, 184)

    sm["selfdriveStateSP"].mads.state = "overriding"
    assert settings.state_color(sm, STARTED_FRAME, True) == (146, 153, 163)

  def test_longitudinal_override_has_priority_during_engagement(self):
    settings = DrivingHudSettings()
    sm = DrivingMessages()
    sm["onroadEvents"] = [SimpleNamespace(overrideLateral=False, overrideLongitudinal=True)]
    sm["carControl"].longActive = False
    assert settings.state_color(sm, STARTED_FRAME, True) == (146, 153, 163)
    assert settings.state_color(sm, STARTED_FRAME, False) == (38, 143, 255)

    sm["carControl"].enabled = sm["carControl"].latActive = False
    assert settings.state_color(sm, STARTED_FRAME, True) is None

  def test_custom_color_and_master_toggle(self):
    sm = DrivingMessages()
    settings = replace(DrivingHudSettings(), both_color=0x24D4DC)
    assert settings.state_color(sm, STARTED_FRAME, True) == (36, 212, 220)
    assert replace(settings, dynamic_colors=False).state_color(sm, STARTED_FRAME, True) is None

  def test_outdated_control_data_disables_color(self):
    sm = DrivingMessages()
    sm.recv_frame["carControl"] = STARTED_FRAME - 1
    assert DrivingHudSettings().state_color(sm, STARTED_FRAME, True) is None

  def test_lead_readings_convert_units_and_use_ego_speed_for_gap(self):
    sm = DrivingMessages()
    sm["radarState"].leadOne.vLead = 15.0
    assert lead_readings(sm, STARTED_FRAME) == ("98 ft", "34 mph", "1.5 s")
    sm["carState"].vEgo = 0.0
    assert lead_readings(sm, STARTED_FRAME) == ("98 ft", "34 mph", UNAVAILABLE)

  def test_unavailable_lead_readings(self):
    for reason in ("no lead", "stale", "invalid", "invalid distance"):
      with self.subTest(reason=reason):
        sm = DrivingMessages()
        if reason == "no lead":
          sm["radarState"].leadOne.present = False
        elif reason == "stale":
          sm.alive["radarState"] = False
        elif reason == "invalid":
          sm.valid["radarState"] = False
        else:
          sm["radarState"].leadOne.dRel = float("nan")
        assert lead_readings(sm, STARTED_FRAME) == (UNAVAILABLE,) * 3
