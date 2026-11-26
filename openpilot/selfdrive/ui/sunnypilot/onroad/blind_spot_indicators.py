"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.common.filter_simple import FirstOrderFilter


class BlindSpotIndicators:
  def __init__(self):
    self._blind_spot_left_alpha_filter = FirstOrderFilter(0, 0.15, 1 / gui_app.target_fps)
    self._blind_spot_right_alpha_filter = FirstOrderFilter(0, 0.15, 1 / gui_app.target_fps)

  def update(self) -> None:
    sm = ui_state.sm
    CS = sm['carState']

    self._blind_spot_left_alpha_filter.update(1.0 if CS.leftBlindspot else 0.0)
    self._blind_spot_right_alpha_filter.update(1.0 if CS.rightBlindspot else 0.0)

  def render(self, rect: rl.Rectangle) -> None:
    if not ui_state.blindspot:
      return

    border_width = 6
    for x, alpha in ((rect.x, self._blind_spot_left_alpha_filter.x),
                     (rect.x + rect.width - border_width, self._blind_spot_right_alpha_filter.x)):
      if alpha > 0.01:
        rl.draw_rectangle_rec(rl.Rectangle(x, rect.y, border_width, rect.height), rl.Color(255, 0, 0, int(255 * alpha)))
