import {NumberFormatter, StringFormatter} from "models/widgets/tables/cell_formatters"

export class DpxNumberFormatter extends NumberFormatter
  type: 'DpxNumberFormatter'

  doFormat: (row, cell, value, columnDef, dataContext) ->
    if value == null or isNaN(value)
        return ""
    return super(row, cell, value, columnDef, dataContext)
