import math
from dataclasses import dataclass


RGB = tuple[int, int, int]
WHITE = (255, 255, 255)
BOTH_DEFAULT = 0x20D875
LATERAL_DEFAULT = 0x268FFF
LONGITUDINAL_DEFAULT = 0xF44AB8
OVERRIDE_DEFAULT = 0x9299A3


def message_is_current(sm, service: str, started_frame: int) -> bool:
  return sm.alive[service] and sm.valid[service] and sm.recv_frame[service] >= started_frame


def unpack_rgb(color: int) -> RGB:
  return (color >> 16, (color >> 8) & 0xFF, color & 0xFF)


def acceleration_wheel_color(sm, started_frame: int) -> RGB:
  if not message_is_current(sm, "carState", started_frame):
    return WHITE
  acceleration = sm["carState"].aEgo
  if not math.isfinite(acceleration):
    return WHITE
  if acceleration > 0.15:
    return (67, 224, 135)
  if acceleration < -0.15:
    return (245, 70, 70)
  return WHITE


@dataclass(frozen=True)
class DrivingHudSettings:
  lead_stats: bool = True
  dynamic_colors: bool = True
  color_path: bool = True
  color_indicators: bool = True
  both_color: int = BOTH_DEFAULT
  lateral_color: int = LATERAL_DEFAULT
  longitudinal_color: int = LONGITUDINAL_DEFAULT
  override_color: int = OVERRIDE_DEFAULT

  @classmethod
  def from_params(cls, params) -> 'DrivingHudSettings':
    def read_color(key: str, default: int) -> int:
      value = params.get(key, return_default=True)
      return value if isinstance(value, int) and 0 <= value <= 0xFFFFFF else default

    return cls(
      lead_stats=bool(params.get("MiciLeadStats", return_default=True)),
      dynamic_colors=bool(params.get("MiciDynamicDrivingColors", return_default=True)),
      color_path=bool(params.get("MiciColorDrivingPath", return_default=True)),
      color_indicators=bool(params.get("MiciColorDrivingIndicators", return_default=True)),
      both_color=read_color("MiciDrivingColorBoth", BOTH_DEFAULT),
      lateral_color=read_color("MiciDrivingColorLateral", LATERAL_DEFAULT),
      longitudinal_color=read_color("MiciDrivingColorLongitudinal", LONGITUDINAL_DEFAULT),
      override_color=read_color("MiciDrivingColorOverride", OVERRIDE_DEFAULT),
    )

  def state_color(self, sm, started_frame: int, has_longitudinal_control: bool) -> RGB | None:
    if not self.dynamic_colors:
      return None
    if not all(message_is_current(sm, service, started_frame) for service in ("carControl", "carState", "onroadEvents")):
      return None

    control = sm["carControl"]
    events = sm["onroadEvents"]
    # Longitudinal is already inactive during a gas override.
    long_override = control.enabled and has_longitudinal_control and any(event.overrideLongitudinal for event in events)
    lat_override = control.latActive and (sm["carState"].steeringPressed or any(event.overrideLateral for event in events))
    if message_is_current(sm, "selfdriveStateSP", started_frame):
      mads = sm["selfdriveStateSP"].mads
      lat_override = lat_override or (mads.available and mads.enabled and mads.state == "overriding")

    if lat_override or long_override:
      return unpack_rgb(self.override_color)
    if control.latActive and control.longActive:
      return unpack_rgb(self.both_color)
    if control.latActive:
      return unpack_rgb(self.lateral_color)
    if control.longActive:
      return unpack_rgb(self.longitudinal_color)
    return None
