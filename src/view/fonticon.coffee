import * as p from "core/properties"

import {AbstractIcon} from "models/widgets/abstract_icon"
import {WidgetView} from "models/widgets/widget"

export class FontIconView extends WidgetView
  tagName: "span"

  initialize: (options) ->
    super(options)
    @render()
    @connect(@model.change, @render)

  render: () ->
    super()
    @el.className = "" # erase all CSS classes if re-rendering
    @el.classList.add("icon-dpx-#{@model.iconname}")
    return @

export class FontIcon extends AbstractIcon
  type: "FontIcon"
  default_view: FontIconView

  @define {
    iconname: [ p.String, "cog" ]
  }
