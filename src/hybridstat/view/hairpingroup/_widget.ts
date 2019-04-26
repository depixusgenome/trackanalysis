import * as p           from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

declare function jQuery(...args: any[]): any

export class DpxDiscardedBeadsView extends WidgetView {
    on_change_input(evt): void {
        jQuery(this.el).find(`#dpx-gb-${evt}`).val(`${this.model[evt]}`)
    }

    connect_signals(): void {
        super.connect_signals()
        for(let evt of this._inputs)
            this.connect(
                this.model.properties[evt].change,
                ((e) => (() => this.on_change_input(e)))(evt)
            )
        this.connect(this.model.properties.frozen.change, () => this.render())
    }

    render(): void {
        super.render()
        const dbal  :string   = 'data-balloon="'
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
            el.change((e) => this.model[e.target.id.slice(7)] = e.target.value)
        }
    }

    get_width_height(): [int, int] {
        return [super.get_width_height()[0], 30]
    }

    get_height(): int { return 30 }

    _mkinp(name): string {
        let disabled: string = ' disabled=true'
        if((name != 'forced') || this.model.hassequence)
            disabled = this.model.frozen ? ' disabled=true' : ''
        const place = this.model[name+'help']
        return  `<input id='dpx-gb-${name}'`+
            ` class='dpx-gb-freeze bk-widget-form-input'`+
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

        this.define({
            frozen:        [p.Bool,   true],
            hassequence:   [p.Bool,   false],
            discarded:     [p.String, ''],
            discardedhelp: [p.String, ''],
            forced:        [p.String, ''],
            forcedhelp:    [p.String, '']
        })
    }
}
DpxDiscardedBeads.initClass()
