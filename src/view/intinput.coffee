import * as _ from "underscore"

import {build_views} from "core/build_views"
import {logger} from "core/logging"
import * as p from "core/properties"

import {InputWidget, InputWidgetView} from "models/widgets/input_widget"
import template from "./intinput_template"


export class IntInputView extends InputWidgetView
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
    value = parseInt(@$el.find('input').val())
    if isNaN(value)
        @$el.find('input').val(model.value)
    else
        logger.debug("widget/int_input: value = #{value}")
        @model.value = value
    super()

export class IntInput extends InputWidget
  type: "IntInput"
  default_view: IntInputView

  @define {
      value: [ p.Int, 0 ]
      minvalue: [p.Int, 0]
      maxvalue: [p.Int, 10]
      placeholder: [ p.String, "" ]
    }
