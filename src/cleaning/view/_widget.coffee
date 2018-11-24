import {build_views}    from "core/build_views"
import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

export class DpxCleaningView extends WidgetView
    tagName: "div"

    on_change_frozen: () ->
        $(@el).find('.dpx-cl-freeze').prop('disabled', @model.frozen)

    on_input: (evt) ->
        @model[evt] = Number($(@el).find("#dpx-cl-#{evt}").val())

    on_change_input: (evt) ->
        $(@el).find("#dpx-cl-#{evt}").val("#{@model[evt]}")

    connect_signals: () ->
        super()
        @connect(@model.properties.subtracted.change,
                 () => $(@el).find("#dpx-cl-subtracted").val("#{@model.subtracted}"))
        for evt in @cl_inputs
            @connect(@model.properties[evt].change,
                     do (event = evt, me = @) -> (val) -> me.on_change_input(event))
        @connect(@model.properties.frozen.change, () => @on_change_frozen())
        @connect(@model.properties.fixedbeads.change, () => @render())

    render: () ->
        super()
        dbal  = 'data-balloon="'
        pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        ttips = [dbal+'Average of listed bead is subtracted from other beads'+pos,
                 dbal+'Adds the current bead to the list'+pos,
                 dbal+'Values too far are deleted '+pos,
                 dbal+'Cycles with a range of values to small or too big are deleted'+pos,
                 dbal+'Values with a high derivate are deleted'+pos,
                 dbal+'Underpopulated cycles are deleted'+pos,
                 dbal+'Constant or noisy cycles are deleted'+pos,
                 dbal+'Enough cycles should reach 0 or the bead is discarded'+pos]

        html = "<table><tr><td>Fixed beads</td>"+
                       "<td id='dpx-cl-fixedbeads' style='width:350px;'>"+
                            "#{@model.fixedbeads}</td></tr>"+
                   "<tr><td #{ttips[0]}>Subtracted</td>"+
                       "<td><div  class='dpx-span'>#{@mk_txt("subtracted")}"+
                            "#{@mk_btn("add", "╋", ttips[1])}</div></td></tr>"+
               "</table>"+
               "<table><tr><td #{ttips[2]}>|z| ≤</td>"+
                     "<td>#{@mk_inp("maxabsvalue", 10.0, 0.1)}</td>"+
                     "<td #{ttips[4]}>|dz/dt| ≤</td>"+
                     "<td>#{@mk_inp("maxderivate", 10.0, 0.1)}</td></tr>"+
                 "<tr><td></td>"+
                     "<td>#{@mk_inp("minextent", 10.0, 0.05)}</td>"+
                     "<td #{ttips[3]}>≤ Δz ≤</td>"+
                     "<td>#{@mk_inp("maxextent", 10.0, 0.05)}</td></tr>"+
                 "<tr><td></td>"+
                     "<td>#{@mk_inp("minhfsigma", 0.05, 0.0001)}</td>"+
                     "<td #{ttips[6]}>≤ σ[HF] ≤</td>"+
                     "<td>#{@mk_inp("maxhfsigma", 0.05,  0.001)}</td></tr>"+
                 "<tr><td #{ttips[5]}>% good  ≥</td>"+
                     "<td>#{@mk_inp("minpopulation", 100, 0.1)}</td>"+
                     "<td #{ttips[7]}>Non-closing cycles (%)</td>"+
                     "<td>#{@mk_inp("maxsaturation", 100.0, 1.0)}</td></tr>"+
                 "</table>"


        @el.innerHTML = html
        elem = $(@el)

        elem.find("#dpx-cl-subtracted").change((e) => @model.subtracted = e.target.value)
        elem.find("#dpx-cl-add").click(() => @model.subtractcurrent =  @model.subtractcurrent+1)
        for evt in @cl_inputs
            el = elem.find("#dpx-cl-#{evt}")
            el.change((e) => @model[e.target.id[7...]] = Number(e.target.value))
        return @

    cl_inputs: ['maxabsvalue', 'maxderivate', 'minpopulation', 'minhfsigma',
                'maxhfsigma', 'minextent', 'maxextent', 'maxsaturation']

    mk_inp: (name, maxv = 100, dv = 0.1) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-cl-#{name}'"+
                    " class='dpx-cl-freeze bk-widget-form-input'"+
                    " type='number' min=0 max=#{maxv} step=#{dv} "+
                    " value=#{@model[name]}#{disabled}>"

    mk_txt: (name, placeholder = '') ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-cl-#{name}'"+
                    " type='text' class='dpx-cl-freeze bk-widget-form-input'"+
                    " value='#{@model[name]}'#{disabled}"+
                    " placeholder='#{placeholder}'>"

    mk_btn: (name, label, ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        str = "<button type='button' id='dpx-cl-#{name}' #{ttip} "+
              "class='dpx-cl-freeze bk-bs-btn bk-bs-btn-default'#{disabled}>"+
              "#{label}</button>"
        return str

export class DpxCleaning extends Widget
    default_view: DpxCleaningView
    type:         "DpxCleaning"

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-cleaning", "dpx-widget"]

    onchangebounds: () ->
        trng       = @figure.extra_x_ranges['time']
        xrng       = @figure.x_range
        trng.start = xrng.start/@framerate
        trng.end   = xrng.end  /@framerate

    @define {
        frozen: [p.Bool, true],
        framerate: [p.Number, 30],
        figure: [p.Instance],
        fixedbeads: [p.String, ""],
        subtracted: [p.String, ""],
        subtractcurrent: [p.Number, 0],
        maxabsvalue: [p.Number, 5],
        maxderivate: [p.Number, 2],
        minpopulation: [p.Number, 80],
        minhfsigma: [p.Number, 1e-4],
        maxhfsigma: [p.Number, 1e-2],
        minextent: [p.Number, .25],
        maxextent: [p.Number, 2.0],
        maxsaturation: [p.Number, 20],
    }
