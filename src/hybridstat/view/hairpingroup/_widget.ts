import * as p           from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

declare function jQuery(...args: any[]): any
declare var Bokeh: any

export class DpxDiscardedBeadsView extends WidgetView {
    model: DpxDiscardedBeads
    _inputs: string[]
    on_change_input(evt:string): void {
        jQuery(this.el).find(`#dpx-gb-${evt}`).val(`${this.model[evt]}`)
    }

    connect_signals(): void {
        super.connect_signals()
        for(let evt of this._inputs)
            this.connect(
                this.model.properties[evt].change,
                ((e:string) => (() => this.on_change_input(e)))(evt)
            )
        this.connect(this.model.properties.frozen.change, () => this.render())
    }

    render(): void {
        super.render()
        const dbal  :string   = 'aria-label="'
        const pos   :string   = '" data-balloon-length="medium" data-balloon-pos="right"'
        const ttips :string[] = [
            dbal+'Force beads to fit a specifi hairpin'+pos,
            dbal+'Discard beads from the display'+pos,
        ]

        const elem = jQuery(this.el)
        elem.html(
            "<table>"+
            `<tr><td ${ttips[0]}>Forced</td><td>${this._mkinp(`forced`)}</td></tr>`+
            `<tr><td ${ttips[1]}>Discarded</td><td>${this._mkinp(`discarded`)}</td></tr>`+
            "</table>"
        )
        for(let evt of this._inputs)
        {
            const el = elem.find(`#dpx-gb-${evt}`)
            el.change((e:Event) => {
                let t = e.target as any as {id: string, value: string}
                this.model[t.id.slice(7)] = t.value
            })
        }
    }

    get_height(): number { return 30 }

    _mkinp(name: string): string {
        const bkclass  = Bokeh.version != '1.0.4' ? ' bk ' : ''
        let disabled: string = ' disabled=true'
        if((name != 'forced') || this.model.hassequence)
            disabled = this.model.frozen ? ' disabled=true' : ''
        const place = this.model[name+'help']
        return  `<input id='dpx-gb-${name}'`+
            ` class='dpx-gb-freeze ${bkclass} bk-input'`+
            ` type='text' value='${this.model[name]}'${disabled} `+
            ` placeholder='${place}'>`

    }

    static initClass(): void {
        this.prototype.tagName = "div"
        this.prototype._inputs = ['discarded', 'forced']
    }
}
DpxDiscardedBeadsView.initClass()

export namespace DpxDiscardedBeads {
    export type Attrs = p.AttrsOf<Props>

    export type Props = Widget.Props & {
        frozen:        p.Property<boolean>
        hassequence:   p.Property<boolean>
        discarded:     p.Property<string>
        discardedhelp: p.Property<string>
        forced:        p.Property<string>
        forcedhelp:    p.Property<string>
        [key:string]:  p.Property<any>
    }
}

export interface DpxDiscardedBeads extends DpxDiscardedBeads.Attrs {}

export class DpxDiscardedBeads extends Widget {
    properties: DpxDiscardedBeads.Props
    constructor(attrs?: Partial<DpxDiscardedBeads.Attrs>) { super(attrs); }

    static initClass(): void {
        this.prototype.type= 'DpxDiscardedBeads'
        this.prototype.default_view= DpxDiscardedBeadsView
        this.override({
            css_classes : ["dpx-row", "dpx-widget", "dpx-gb-widget", "dpx-span"]
        })

        this.define<DpxDiscardedBeads.Props>({
            frozen:        [p.Boolean, true],
            hassequence:   [p.Boolean, false],
            discarded:     [p.String,  ''],
            discardedhelp: [p.String,  ''],
            forced:        [p.String,  ''],
            forcedhelp:    [p.String,  '']
        })
    }
}
DpxDiscardedBeads.initClass()
