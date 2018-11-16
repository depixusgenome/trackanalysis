import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"

import {WidgetView, Widget} from "models/widgets/widget"

export class DpxDAQToolbarView extends WidgetView
    tagName: "div"

    on_zmag:    () ->
        val = $(@el).find('#dpx-tb-zmag').val()
        @model.zmag = parseFloat(val)

    on_speed:    () ->
        val = $(@el).find('#dpx-tb-speed').val()
        @model.speed = parseFloat(val)

    on_change_protocol:  () ->
        $(@el).find('.dpx-tb-protocol')    .prop('disabled', @model.protocol != 'manual')
        $(@el).find('#dpx-tb-manual')      .prop('disabled', false)
        $(@el).find('.dpx-tb-manual-input').prop('disabled', @model.protocol != 'manual')
        $(@el).find('#dpx-tb-record')      .prop('disabled', @model.recording)
        $(@el).find('#dpx-tb-stop')        .prop('disabled', !@model.recording)

        $(@el).find('.dpx-tb-protocol').removeClass('dpx-protocol-active')
        $(@el).find("#dpx-tb-#{@model.protocol}").addClass('dpx-protocol-active')

    on_change_zranges: () ->
        itm = document.getElementById("dpx-tb-zmag")
        itm.setAttribute("min",   @model.zmagmin.toFixed(3))
        itm.value = @model.zmag.toFixed(3)
        itm.setAttribute("max",   @model.zmagmax.toFixed(3))
        itm.setAttribute("step",  @model.zinc.toFixed(3))

    on_change_sranges: () ->
        itm = document.getElementById("dpx-tb-speed")
        itm.setAttribute("min",   @model.speedmin)
        itm.value = @model.speed.toFixed(4)
        itm.setAttribute("max",   @model.speedmax)
        itm.setAttribute("step",  @model.speedinc)

    on_change_message: () ->
        $(@el).find('#dpx-tb-message').html(@model.message)

    connect_signals: () ->
        super()
        @connect(@model.properties.message.change,   () => @on_change_message())
        @connect(@model.properties.protocol.change,  () => @on_change_protocol())
        @connect(@model.properties.recording.change, () => @on_change_protocol())
        @connect(@model.properties.zmagmin.change,   () => @on_change_zranges())
        @connect(@model.properties.zmag.change,      () => @on_change_zranges())
        @connect(@model.properties.zmagmax.change,   () => @on_change_zranges())
        @connect(@model.properties.zinc.change,      () => @on_change_zranges())
        @connect(@model.properties.speedmin.change,  () => @on_change_sranges())
        @connect(@model.properties.speed.change,     () => @on_change_sranges())
        @connect(@model.properties.speedmax.change,  () => @on_change_sranges())
        @connect(@model.properties.speedinc.change,  () => @on_change_sranges())

    make_btn: (name, label, ttip = '', freeze = 'dpx-tb-protocol') ->
        if ttip == ''
            str = "<button type='button' id='dpx-tb-#{name}' "+
                  "class='#{freeze} bk-bs-btn bk-bs-btn-default'>#{label}</button>"
        else
            str = "<button type='button' id='dpx-tb-#{name}' "+
                  "class='#{freeze} bk-bs-btn bk-bs-btn-default' "+
                  "data-balloon='#{ttip}' "+
                    'data-balloon-length="medium" data-balloon-pos="right">'+
                  label+'</button>'
        return str

    render: () ->
        super()
        mdl  = @model
        if @model.hasquit
            quit = "<div class='dpx-col-12'>#{@make_btn('quit', 'Quit', '')}</div>"
        else
            quit =''

        ttips = ['Manual mode' ,
                 'Start ramp cycles',
                 'Start probing cycles',
                 'Start recording',
                 'Stop recording',
                 'Change the network configuration']

        html = "<label>Z magnet</label><input id='dpx-tb-zmag'"+
                   " class='dpx-tb-manual-input bk-widget-form-input'"+
                   " type='number' min=#{mdl.zmagmin} max=#{mdl.zmagmax} "+
                   "step=#{mdl.zinc} value=#{mdl.zmag}></input>"+
               "<label>Z speed</label><input id='dpx-tb-speed'"+
                   " class='dpx-tb-manual-input bk-widget-form-input'"+
                   " type='number' min=#{mdl.speedmin} max=#{mdl.speedmax} "+
                   "step=#{mdl.speedinc} value=#{mdl.speed}></input>"+
               @make_btn('manual', 'Manual', ttips[0])+
               @make_btn('ramp', 'Ramps', ttips[1])+
               @make_btn('probe', 'Probing', ttips[2])+
               @make_btn('record', 'Record', ttips[3], '')+
               @make_btn('stop', 'Stop', ttips[4], '')+
               "<div id='dpx-tb-message' class='bk-markup'>"+
                   "#{mdl.message}</div>"+
               "#{quit}"+
               @make_btn('network', 'Network', ttips[5])

        elem = $(@el)
        elem.html(html)
        elem.find('#dpx-tb-zmag').change(() => @on_zmag())
        elem.find('#dpx-tb-speed').change(() => @on_speed())
        elem.find('#dpx-tb-manual').click(() => @model.manual = @model.manual+1)
        elem.find('#dpx-tb-ramp').click(() => @model.ramp = @model.ramp+1)
        elem.find('#dpx-tb-probe').click(() => @model.probing = @model.probing+1)
        elem.find('#dpx-tb-record').click(() => @model.record = @model.record+1)
        elem.find('#dpx-tb-stop').click(() => @model.stop = @model.stop+1)
        elem.find('#dpx-tb-quit').click(() => @model.quit = @model.quit+1)
        elem.find('#dpx-tb-network').click(() => @model.network = @model.network+1)

        @on_change_protocol()
        return @

    get_width_height: () ->
        [width, height] = LayoutDOMView::get_width_height()
        return [width, 30]

    get_height: () -> 30

export class DpxDAQToolbar extends Widget
    type: 'DpxDAQToolbar'
    default_view: DpxDAQToolbarView

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-row", "dpx-widget", "dpx-tb", "dpx-span"]

    @define {
        protocol:   [p.String,  'manual']
        recording:  [p.Bool,    false]
        manual:     [p.Number,  -1]
        ramp:       [p.Number,  -1]
        probing:    [p.Number,  -1]
        record:     [p.Number,  -1]
        stop:       [p.Number,  -1]
        quit:       [p.Number,  -1]
        network:    [p.Number,  -1]
        message:    [p.String,  '']
        hasquit:    [p.Bool,    false]
        zmagmin:    [p.Number,   0.0]
        zmag:       [p.Number,   .5]
        zmagmax:    [p.Number,   1.0]
        zinc:       [p.Number,   .1]
        speedmin:   [p.Number,   0.125]
        speed:      [p.Number,   .125]
        speedmax:   [p.Number,   1.0]
        speedinc:   [p.Number,   .1]

    }
