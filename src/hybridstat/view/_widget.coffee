import {build_views}    from "core/build_views"
import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

export class DpxFitParamsView extends WidgetView
    tagName: "div"

    _set_lock: () ->
        elem = $(@el)
        elem = elem.find("#dpx-pk-ls-icon")
        elem.removeClass()
        if @model.locksequence
            elem.addClass("icon-dpx-lock")
        else
            elem.addClass("icon-dpx-unlocked")

    on_change_frozen: () ->
        $(@el).find('.dpx-fp-freeze').prop('disabled', @model.frozen)

    on_lock: (evt) ->
        @model.locksequence = !@model.locksequence
        @_set_lock()

    on_input: (evt) ->
        id = evt.target.id[7...]
        @model[id] = evt.target.value

    on_change_input: (evt) ->
        itm = $(@el).find("#dpx-pk-#{evt}")
        if "#{evt}" == "locksequence"
            @_set_lock()
        else
            itm.val("#{@model[evt]}")

    connect_signals: () ->
        super()
        for evt in @cl_inputs
            @connect(@model.properties[evt].change,
                     do (event = evt, me = @) -> (val) -> me.on_change_input(event))
        @connect(@model.properties.frozen.change, () => @render())

    render: () ->
        super()
        dbal  = 'data-balloon="'
        pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        ttips = [dbal+'Force a stretch value (base/µm)'+pos,
                 dbal+'Force a bias value (µm)'+pos,
                 dbal+'Lock the sequence to the currently selected one'+pos]

        html  = "<div class='dpx-span'>"+
                    @mk_inp("stretch", "Stretch", ttips[0])+
                    @mk_inp("bias",    "Bias (µm)", ttips[1])+
                    @mk_check(ttips[2])+
                "</div>"
                

        @el.innerHTML = html

        elem = $(@el)
        for evt in ["stretch", "bias"]
            elem.find("#dpx-pk-#{evt}").change((e) => @on_input(e))
        elem.find("#dpx-pk-locksequence").click(() => @on_lock())
        return @

    cl_inputs: ["stretch", "bias", "locksequence"]

    mk_inp: (name, label, ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-pk-#{name}' #{ttip}"+
                    " class='dpx-fp-freeze bk-widget-form-input' type='text' "+
                    " placeholder='#{label}' value='#{@model[name]}'#{disabled}>"

    mk_check: (ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        icon     = if @model.locksequence then 'lock' else 'unlocked'
        return "<button type='button' id='dpx-pk-locksequence' #{ttip} "+
              "class='dpx-fp-freeze bk-bs-btn bk-bs-btn-default'#{disabled}>"+
              "<span class='icon-dpx-#{icon}'#{disabled} id='dpx-pk-ls-icon'>Hairpin</span></button>"

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
