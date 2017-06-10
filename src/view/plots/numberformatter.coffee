import {NumberFormatter, StringFormatter} from "models/widgets/cell_formatters"

export class DpxNumberFormatter extends NumberFormatter
  type: 'DpxNumberFormatter'

  doFormat: (row, cell, value, columnDef, dataContext) ->
    if value or value == 0
        return super(row, cell, value, columnDef, dataContext)

    StringFormatter.prototype.doFormat.apply(this, [row, cell, null, columnDef, dataContext])
