import * as p           from "core/properties"

import {WidgetView, Widget} from "models/widgets/widget"

export class DpxDiscardedBeadsView extends WidgetView
    tagName: "div"

    on_change_frozen:  () ->
        $(@el).find('.dpx-gb-freeze').prop('disabled', @model.frozen)
        if !@model.frozen && !@model.hassequence
            $('#dpx-gb-forced').prop('disabled', true)
            console.log("frozen", @model.frozen, false)
        else
            console.log("frozen", @model.frozen, true)

    on_change_input: (evt) ->
        $(@el).find("#dpx-gb-#{evt}").val("#{@model[evt]}")

    connect_signals: () ->
        super()
        for evt in @_inputs
            @connect(@model.properties[evt].change,
                     do (event = evt, me = @) -> (val) -> me.on_change_input(event))

    render: () ->
        super()
        dbal  = 'data-balloon="'
        pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        ttips = [
            dbal+'Force beads to fit a specifi hairpin'+pos,
            dbal+'Discard beads from the display'+pos,
        ]
        html = "<table>"+
               "<tr><td #{ttips[0]}>Forced</td><td>#{@_mkinp("forced")}</td></tr>"+
               "<tr><td #{ttips[1]}>Discarded</td><td>#{@_mkinp("discarded")}</td></tr>"+
               "</table>"

        elem = $(@el)
        elem.html(html)
        for evt in @_inputs
            el = elem.find("#dpx-gb-#{evt}")
            el.change((e) => @model[e.target.id[7...]] = e.target.value)
        return @

    get_width_height: () ->
        [width, height] = LayoutDOMView::get_width_height()
        return [width, 30]

    get_height: () -> 30

    _inputs: ['discarded', 'forced']
    _mkinp: (name) ->
        if (name == 'forced') && !@model.hassequence
            disabled = ' disabled=true'
        else
            disabled = if @model.frozen then ' disabled=true' else ''
        console.log("--", name, disabled)
        place    = @model[name+'help']
        return  "<input id='dpx-gb-#{name}'"+
                    " class='dpx-gb-freeze bk-widget-form-input'"+
                    " type='text' value='#{@model[name]}'#{disabled} "+
                    " placeholder='#{place}'>"

export class DpxDiscardedBeads extends Widget
    type: 'DpxDiscardedBeads'
    default_view: DpxDiscardedBeadsView

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-row", "dpx-widget", "dpx-gb-widget", "dpx-span"]

    @define {
        frozen:        [p.Bool,   true],
        hassequence:   [p.Bool,   false],
        discarded:     [p.String, ''],
        discardedhelp: [p.String, ''],
        forced:        [p.String, ''],
        forcedhelp:    [p.String, '']
    }
