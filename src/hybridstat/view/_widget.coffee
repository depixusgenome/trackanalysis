import {build_views}    from "core/build_views"
import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

export class DpxFitParamsView extends WidgetView
    tagName: "div"

    on_change_frozen: () ->
        $(@el).find('.dpx-pk-freeze').prop('disabled', @model.frozen)

    on_input: (evt) ->
        id = evt.target.id[7...]
        if id == "locksequence"
            @model[id] = ($(@el).find("#dpx-pk-locksequence").prop("checked"))
        else
            @model[id] = evt.target.value

    on_change_input: (evt) ->
        itm = $(@el).find("#dpx-pk-#{evt}")
        if "#{evt}" == "locksequence"
            itm.prop("checked", @model.locksequence)
        else
            itm.val("#{@model[evt]}")

    connect_signals: () ->
        super()
        for evt in @cl_inputs
            @connect(@model.properties[evt].change,
                     do (event = evt, me = @) -> (val) -> me.on_change_input(event))
        @connect(@model.properties.frozen.change, () => @on_change_frozen())

    render: () ->
        super()
        dbal  = 'data-balloon="'
        pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        ttips = [dbal+'Force a stretch value'+pos,
                 dbal+'Force a bias value'+pos,
                 dbal+'Lock the sequence to the currently selected one'+pos]

        html  = "<div class='dpx-span'>"+
                    @mk_check("locksequence", "Lock sequence", ttips[2])+
                    @mk_inp("stretch", "Stretch", ttips[0])+
                    @mk_inp("bias",    "Bias (µm)", ttips[1])+
                "</div>"

        @el.innerHTML = html

        elem = $(@el)
        for evt in @cl_inputs
            elem.find("#dpx-pk-#{evt}").change((e) => @on_input(e))
        return @

    cl_inputs: ["stretch", "bias", "locksequence"]

    mk_inp: (name, label, ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-pk-#{name}' #{ttip}"+
                    " class='dpx-pk-freeze bk-widget-form-input' type='text' "+
                    " placeholder='#{label}' value='#{@model[name]}'#{disabled}>"

    mk_check: (name, label, ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        checked  = if @model[name] then ' checked=true' else ''
        return "<label class='bk-bs-checkbox-inline' id='dpx-pk-ls-label'>"+
                    "#{label}"+
                    "<input id='dpx-pk-#{name}' #{ttip}"+
                        " class='dpx-pk-freeze bk-widget-form-input' type='checkbox' "+
                        " #{checked}#{disabled}></input></label>"

export class DpxFitParams extends Widget
    default_view: DpxFitParamsView
    type:         "DpxFitParams"

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-params", "dpx-widget"]

    @define {
        frozen:       [p.Bool, true],
        stretch:      [p.String, ""],
        bias:         [p.String, ""],
        locksequence: [p.Bool]
    }
