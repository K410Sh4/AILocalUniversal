use kia_cognitive_runtime::RuntimeHost;
use std::io::{self, BufRead, Write};

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut output = io::BufWriter::new(stdout.lock());
    let mut host = RuntimeHost::default();

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(line) => line,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }

        let (response, should_shutdown) = host.process_line(&line);
        if serde_json::to_writer(&mut output, &response).is_err()
            || writeln!(&mut output).is_err()
            || output.flush().is_err()
        {
            break;
        }
        if should_shutdown {
            break;
        }
    }
}
