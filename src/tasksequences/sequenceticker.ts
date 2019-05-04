import {BasicTicker} from "models/tickers/basic_ticker"
import {TickSpec}    from "models/tickers/ticker"
import *             as p from "core/properties"

export namespace SequenceTicker {
    export type Attrs = p.AttrsOf<Props>

    export type Props = BasicTicker.Props & {
        major: p.Property<{[key:string]: number[]}>
        minor: p.Property<{[key:string]: number[]}>
        key:   p.Property<string>
    }
}

export interface SequenceTicker extends SequenceTicker.Attrs {}

export class SequenceTicker extends BasicTicker {
    properties: SequenceTicker.Props
    constructor(attrs?: Partial<SequenceTicker.Attrs>) { super(attrs); }
    static initClass() : void {
        this.prototype.type = 'SequenceTicker'

        this.define<SequenceTicker.Props>({
            major:      [ p.Any, {} ],
            minor:      [ p.Any, {} ],
            key:        [ p.String, '']
        })
    }

    get_ticks_no_defaults(
        data_low: number,
        data_high: number,
        _cross_loc: any,
        desired_n_ticks: number
    ): TickSpec<number> {
        if (!(this.key in this.major))
            return super.get_ticks_no_defaults(data_low, data_high, _cross_loc, desired_n_ticks)
        else
            return {
                major: this.major[this.key],
                minor: this.minor[this.key]
            }
    }
}
SequenceTicker.initClass()
