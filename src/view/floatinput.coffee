import {build_views} from "core/build_views"
import {logger} from "core/logging"
import * as p from "core/properties"

import {InputWidget, InputWidgetView} from "models/widgets/input_widget"
import template from "./intinput_template"


export class FloatInputView extends InputWidgetView
  tagName: "div"
  className: "bk-widget-form-group"
  template: template
  events:
    "change input": "change_input"

  initialize: (options) ->
    super(options)
    @_height = null
    @render()
    @listenTo(@model, 'change', @render)

  render: () ->
    super()
    @$el.html(@template(@model.attributes))
    if @model.disabled then @$el.find("input").prop("disabled", true)
    @$el.find("input").width(@model.width-20)
    if @model.height - @$el.find("label").height()-4 > 0
        @$el.find("input").height(@model.height - @$el.find("label").height()-4)
    else
        @$el.find("input").height(@model.height/1.5)
    return @

  change_input: () ->
    value = Number(@$el.find('input').val())
    if isNaN(value)
        @$el.find('input').val(model.value)
    else
        logger.debug("widget/int_input: value = #{value}")
        @model.value = value
    super()

export class FloatInput extends InputWidget
  type: "FloatInput"
  default_view: FloatInputView

  @define {
      value:        [p.Number, 0 ]
      start:        [p.Number, 0]
      step:         [p.Number, 1]
      end:          [p.Number, 10]
      placeholder:  [p.String, "" ]
    }
