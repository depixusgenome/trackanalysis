import {build_views} from "core/build_views"
import * as p from "core/properties"

import {InputWidget, InputWidgetView} from "models/widgets/input_widget"

export class DpxTextInputView extends InputWidgetView
    tagName: "div"
    className: "bk-widget-form-group"
    events:
        "change input": "change_input"

    initialize: (options) ->
        super(options)
        @_height = null
        @render()
        @listenTo(@model, 'change', @render)

    render: () ->
        super()
        mdl   = @model
        style = "margin-right: 5px; margin-top: 9px; margin-left: 5px"
        label = "<tr><td><label for=#{@id}>#{mdl.title}</label></td>"
        input = "<td> <input class='bk-widget-form-input'   type='text'"        +
                      "id=#{@id} name=#{mdl.name}"                              +
                      "placeholder=#{mdl.placeholder} value='#{mdl.value}'"   +
                "></td>"
        @$el.html("<table class='dpx-int-input' style='#{style}'>#{label} #{input}</table>")

        inp = @$el.find("input")
        if mdl.disabled then inp.prop("disabled", true)
        inp.width(mdl.width)
        inp.height(mdl.height)
        return @

    change_input: () ->
        @model.value = @$el.find('input').val()
        super()

export class DpxTextInput extends InputWidget
    type: "DpxTextInput"
    default_view: DpxTextInputView

    @define {
        value:        [p.String, ""]
        placeholder:  [p.String, ""]
    }
