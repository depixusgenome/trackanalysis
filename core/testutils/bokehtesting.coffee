import *        as p    from "core/properties"
import {Model}          from "model"
import {DOMView}        from "core/dom_view"

export class DpxTestLoadedView extends DOMView
    className: "dpx-test"

    connect_signals: () ->
        super()
        console.log("DpxTestLoadedView connect_signals")
        @connect(@model.properties.event_cnt.change, () => @model._press())
        @connect(@model.properties.value_cnt.change, () => @model._change())

export class DpxTestLoaded extends Model
    default_view: DpxTestLoadedView
    type: "DpxTestLoaded"
    constructor : (attributes, options) ->
        super(attributes, options)
        $((e) => @done = 1)

        self = @

        oldlog       = console.log
        console.log  = () -> self._tostr(oldlog, 'debug', arguments)

        oldinfo      = console.info
        console.info = () -> self._tostr(oldinfo, 'info', arguments)

        oldwarn      = console.warn
        console.warn = () -> self._tostr(oldwarn, 'warn', arguments)

    _tostr: (old, name, args) ->
        old.apply(console, args)

        str = ""
        for i in args
            str = str + " " + i
        @[name] = ""
        @[name] = str

    _create_evt: (name) ->
        evt = $.Event(name)
        evt.altKey   = @event.alt
        evt.shiftKey = @event.shift
        evt.ctrlKey  = @event.ctrl
        evt.metaKey  = @event.meta
        evt.key      = @event.key

        return evt

    _press: () ->
        console.debug("pressed key: ", @event.ctrl, @event.key)
        if @model?
            @model.dokeydown?(@_create_evt('keydown'))
            @model.dokeyup?(@_create_evt('keyup'))
        else
            console.log("pressed key but there's no model")

    _change: () ->
        console.debug("changed attribute: ", @attrs, @value)
        if @model?
            mdl = @model
            for i in @attrs
                mdl = mdl[i]

            mdl[@attr] = @value
            if @attrs.length == 0
                @model.properties[@attr].change.emit()
            else
                @model.properties[@attrs[0]].change.emit()
        else
            console.log("changed key but there's no model")

    @define {
        done:  [p.Number, 0]
        event: [p.Any,   {}]
        event_cnt: [p.Int, 0]
        model: [p.Any,   {}]
        attrs: [p.Array, []]
        attr : [p.String, '']
        value: [p.Any,   {}]
        value_cnt: [p.Int, 0]
        debug: [p.String, '']
        warn: [p.String, '']
        info: [p.String, '']
    }
