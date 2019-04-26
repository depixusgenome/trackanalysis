import {BasicTicker} from "models/tickers/basic_ticker"
import *             as p from "core/properties"

export namespace SequenceTicker {
    export type Attrs = p.AttrsOf<Props>

    export type Props = BasicTicker.Props & {
        major: p.Property<number[]>
        minor: p.Property<number[]>
        key:   p.Property<string>
    }
}

export interface SequenceTicker extends SequenceTicker.Attrs {}

export class SequenceTicker extends BasicTicker {
    properties: SequenceTicker.Props
    constructor(attrs?: Partial<SequenceTicker.Attrs>) { super(attrs); }
    static initClass() : void {
        this.prototype.type = 'SequenceTicker'

        this.define({
            major:      [ p.Any, {} ],
            minor:      [ p.Any, {} ],
            key:        [ p.String, '']
        })
    }

    get_ticks_no_defaults(data_low, data_high, cross_loc, desired_n_ticks): void {
        if (!(this.key in this.major))
            return super.get_ticks_no_defaults(data_low, data_high, cross_loc, desired_n_ticks)
        else
            return {
                major: this.major[this.key],
                minor: this.minor[this.key]
            }
    }
}
SequenceTicker.initClass()
