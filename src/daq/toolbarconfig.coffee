import * as p         from "core/properties"
import {ActionTool, ActionToolView} from "models/tools/actions/action_tool"

export class ConfigToolView extends ActionToolView
  model: ConfigTool
  doit: () ->
      @model.configclick += 1

export class ConfigTool extends ActionTool
  properties: ConfigTool.Props

  @initClass: () ->
    @prototype.type         = "ConfigTool"
    @prototype.default_view = ConfigToolView

  tool_name: "Configuration"
  icon: "bk-tool-icon-help"
  @define { configclick: [p.Number, -1] }

ConfigTool.initClass()
