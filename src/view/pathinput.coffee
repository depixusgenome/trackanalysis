import {build_views} from "core/build_views"
import * as p from "core/properties"
import {InputWidget, InputWidgetView} from "models/widgets/input_widget"


export class PathInputView extends InputWidgetView

  connect_signals: () ->
    super()
    @connect(@model.change, @render)

  render: () ->
    super()
    if @model.title
        label = "<label for=#{@model.id}> #{@model.title} </label>"
    else
        label = ""
    txt   = "<input class='bk-widget-form-input' type='text' "             +
            "id=#{@model.id} name=#{@model.name} value='#{@model.value}' " +
            "placeholder='#{@model.placeholder}' />"

    btn   = "<button type='button' "                            +
            "class='bk-bs-btn bk-bs-btn-default' "              +
            "style='margin-left:5px'><span class='icon-dpx-folder-plus'></span>"+
            "</button>"
    $(@el).html("<div class='dpx-span'>#{label}#{txt}#{btn}</div>")

    elem = $(@el)

    inp  = elem.find('input')
    if @model.height
      # TODO - This 35 is a hack we should be able to compute it
      inp.height(@model.height - 35)
    if @model.width
      inp.width(@model.width-50)
    inp.prop("disabled", @model.disabled)
    inp.change(() => @change_input())

    btn = elem.find('button')
    btn.width(5)
    btn.prop("disabled", @model.disabled)
    btn.click(() => @change_click())
    return @

  change_click: () ->
    @model.click = @model.click+1
    super()

  change_input: () ->
    @model.value = $(@el).find('input').val()
    super()

export class PathInput extends InputWidget
  type: "PathInput"
  default_view: PathInputView

  @define {
      value: [ p.String, "" ]
      placeholder: [ p.String, "" ]
      click: [p.Number, 0]
    }
