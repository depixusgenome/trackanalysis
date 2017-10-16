import * as p  from "core/properties"
import {Model} from "model"
import {DOMView} from "core/dom_view"

export class DpxKeyEventView extends DOMView

export class DpxKeyEvent extends Model
    default_view: DpxKeyEventView
    type:"DpxKeyEvent"
    constructor: (attrs, opts) ->
        super(attrs, opts)
        $(document).keydown((e) => @dokeydown(e))

    dokeydown: (evt) ->
        val = ""
        for name, kw of {alt: 'Alt'; shift: 'Shift'; ctrl: 'Control'; meta: 'Meta'}
            if evt[name+'Key']
                 val += "#{kw}-"
        val = if val == (evt.key+'-') then evt.key else val + evt.key
        if val in @keys
            evt.preventDefault()
            evt.stopPropagation()
            @value = val
            @count = @count+1

    @define {
        keys:  [p.Array, []]
        value: [p.String, ""]
        count: [p.Int, 0]
    }
