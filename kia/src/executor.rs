use crate::{ComponentId, CognitiveRequest, NeuralComponent};
use serde_json::Value;
use std::collections::HashMap;

pub trait ComponentExecutor: Send + Sync {
    /// Executa um componente. O adaptador decide como interpretar input.
    fn execute(
        &self,
        request: &CognitiveRequest,
        component: &NeuralComponent,
    ) -> Result<Value, String>;
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
