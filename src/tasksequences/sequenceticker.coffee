import {BasicTicker} from "models/tickers/basic_ticker"
import *             as p from "core/properties"

export class SequenceTicker extends BasicTicker
    type: 'SequenceTicker'

    @define {
        major:      [ p.Any, {} ]
        minor:      [ p.Any, {} ]
        key:        [ p.String, '']
    }

    get_ticks_no_defaults: (data_low, data_high, cross_loc, desired_n_ticks) ->
        if @key not of @major
            return super(data_low, data_high, cross_loc, desired_n_ticks)
        else
            return {
                major: @major[@key]
                minor: @minor[@key]
            }
