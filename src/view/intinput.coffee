import {build_views} from "core/build_views"
import {logger} from "core/logging"
import * as p from "core/properties"

import {InputWidget, InputWidgetView} from "models/widgets/input_widget"

export class DpxIntInputView extends InputWidgetView
    tagName: "div"
    className: "bk-widget-form-group"
    events:
        "change input": "change_input"

    initialize: (options) ->
        super(options)
        @_height = null
        @render()
        @connect(@model.change, @render)

    render: () ->
        super()
        mdl   = @model
        style = "margin-right: 5px; margin-top: 9px; margin-left: 5px"
        label = "<tr><td><label for=#{@id}>#{mdl.title}</label></td>"
        input = "<td> <input class='bk-widget-form-input'   type='number'"  +
                      "id=#{@id}           name=#{mdl.name}"                +
                      "min=#{mdl.start}    max=#{mdl.end}"                  +
                      "step=#{mdl.step}    value=#{mdl.value}"              +
                "></td>"
        @$el.html("<table class='dpx-int-input' style='#{style}'>#{label} #{input}</table>")

        inp = @$el.find("input")
        if mdl.disabled then inp.prop("disabled", true)
        inp.width(mdl.width)
        inp.height(mdl.height)
        return @

    change_input: () ->
        value = @_convert(@$el.find('input').val())
        if isNaN(value)
            @$el.find('input').val(model.value)
        else
            logger.debug("widget/int_input: value = #{value}")
            @model.value = value
        super()

    _convert: parseInt

export class DpxIntInput extends InputWidget
    type: "DpxIntInput"
    default_view: DpxIntInputView

    @define {
        value:        [p.Int, 0 ]
        start:        [p.Int, 0]
        step:         [p.Int, 1]
        end:          [p.Int, 10]
    }
