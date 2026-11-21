use serde::{Deserialize, Serialize};
use std::fmt::{Display, Formatter};

macro_rules! identifier {
    ($name:ident) => {
        #[derive(
            Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize,
        )]
        #[serde(transparent)]
        pub struct $name(pub String);

        impl From<&str> for $name {
            fn from(value: &str) -> Self {
                Self(value.to_owned())
            }
        }

        impl From<String> for $name {
            fn from(value: String) -> Self {
                Self(value)
            }
        }

        impl Display for $name {
            fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
                formatter.write_str(&self.0)
            }
        }

        impl $name {
            pub fn is_valid(&self) -> bool {
                !self.0.trim().is_empty()
                    && self.0.len() <= 128
                    && self.0.chars().all(|character| {
                        character.is_ascii_alphanumeric()
                            || matches!(character, '-' | '_' | '.' | ':')
                    })
            }
        }
    };
}

identifier!(CapabilityId);
identifier!(ComponentId);
