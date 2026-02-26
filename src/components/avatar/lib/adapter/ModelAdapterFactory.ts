import { IModelAdapter } from './IModelAdapter'

export class ModelAdapterFactory {
  private static adapters: IModelAdapter[] = []

  static getAdapter(modelPath: string): IModelAdapter | null {
    for (const adapter of this.adapters) {
      if (adapter.canHandle(modelPath)) {
        return adapter
      }
    }
    return null
  }

  static registerAdapter(adapter: IModelAdapter) {
    this.adapters.push(adapter)
  }
}
