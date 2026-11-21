use crate::{CognitiveRequest, ComponentId, ExecutionControl, NeuralComponent};
use serde_json::Value;
use std::collections::HashMap;

pub trait ComponentExecutor: Send + Sync {
    /// Executa um componente. O adaptador decide como interpretar input.
    fn execute(
        &self,
        request: &CognitiveRequest,
        component: &NeuralComponent,
    ) -> Result<Value, String>;

    /// Variante cooperativa com deadline/cancelamento.
    ///
    /// Adaptadores antigos continuam compatíveis pelo comportamento padrão. Adaptadores
    /// com I/O ou inferência longa devem sobrescrever este método e consultar
    /// control.check() em pontos seguros para interromper o trabalho.
    fn execute_controlled(
        &self,
        request: &CognitiveRequest,
        component: &NeuralComponent,
        control: &ExecutionControl,
    ) -> Result<Value, String> {
        control.check().map_err(|error| error.to_string())?;
        self.execute(request, component)
    }
}

#[derive(Default)]
pub struct ExecutorRegistry {
    executors: HashMap<ComponentId, Box<dyn ComponentExecutor>>,
}

impl ExecutorRegistry {
    pub fn register<E>(&mut self, component_id: ComponentId, executor: E)
    where
        E: ComponentExecutor + 'static,
    {
        self.executors.insert(component_id, Box::new(executor));
    }

    pub fn contains(&self, component_id: &ComponentId) -> bool {
        self.executors.contains_key(component_id)
    }

    pub(crate) fn get(&self, component_id: &ComponentId) -> Option<&dyn ComponentExecutor> {
        self.executors
            .get(component_id)
            .map(|executor| executor.as_ref())
    }
}
