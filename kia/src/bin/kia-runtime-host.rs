use kia_cognitive_runtime::{RuntimeHost, MAX_REQUEST_BYTES};
use std::io::{self, BufRead, Write};

fn read_bounded_line(reader: &mut impl BufRead) -> io::Result<Option<String>> {
    let mut bytes = Vec::with_capacity(8 * 1024);
    let mut oversized = false;

    loop {
        let available = reader.fill_buf()?;
        if available.is_empty() {
            if bytes.is_empty() && !oversized {
                return Ok(None);
            }
            break;
        }

        let newline = available.iter().position(|byte| *byte == b'\n');
        let chunk_len = newline.unwrap_or(available.len());
        let consumed = newline.map_or(available.len(), |index| index + 1);

        if !oversized {
            let remaining = MAX_REQUEST_BYTES
                .saturating_add(1)
                .saturating_sub(bytes.len());
            let take = chunk_len.min(remaining);
            bytes.extend_from_slice(&available[..take]);
            if bytes.len() > MAX_REQUEST_BYTES {
                oversized = true;
                bytes.clear();
            }
        }

        reader.consume(consumed);
        if newline.is_some() {
            break;
        }
    }

    if oversized {
        // Sentinela limitada em memória: RuntimeHost converte isso em request_too_large.
        return Ok(Some("x".repeat(MAX_REQUEST_BYTES + 1)));
    }

    if bytes.last() == Some(&b'\r') {
        bytes.pop();
    }
    String::from_utf8(bytes)
        .map(Some)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
}

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut input = stdin.lock();
    let mut output = io::BufWriter::new(stdout.lock());
    let mut host = RuntimeHost::default();

    while let Ok(Some(line)) = read_bounded_line(&mut input) {
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

#[cfg(test)]
mod tests {
    use super::read_bounded_line;
    use kia_cognitive_runtime::MAX_REQUEST_BYTES;
    use std::io::Cursor;

    #[test]
    fn bounded_reader_preserves_normal_lines_and_crlf() {
        let mut input = Cursor::new(b"{\"ok\":true}\r\nnext\n".to_vec());
        assert_eq!(
            read_bounded_line(&mut input).unwrap().as_deref(),
            Some("{\"ok\":true}")
        );
        assert_eq!(
            read_bounded_line(&mut input).unwrap().as_deref(),
            Some("next")
        );
        assert_eq!(read_bounded_line(&mut input).unwrap(), None);
    }

    #[test]
    fn bounded_reader_discards_oversized_line_and_recovers_next_request() {
        let mut input =
            Cursor::new([vec![b'x'; MAX_REQUEST_BYTES + 100], b"\nnext\n".to_vec()].concat());
        let oversized = read_bounded_line(&mut input).unwrap().unwrap();
        assert_eq!(oversized.len(), MAX_REQUEST_BYTES + 1);
        assert_eq!(
            read_bounded_line(&mut input).unwrap().as_deref(),
            Some("next")
        );
    }

    #[test]
    fn bounded_reader_handles_final_line_without_newline() {
        let mut input = Cursor::new(b"last".to_vec());
        assert_eq!(
            read_bounded_line(&mut input).unwrap().as_deref(),
            Some("last")
        );
        assert_eq!(read_bounded_line(&mut input).unwrap(), None);
    }
}
