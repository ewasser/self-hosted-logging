def rows(n: int, entries):

    current_row = []

    for entry in entries:
        current_row.append(entry)
        if len(current_row) == n:
            yield current_row
            current_row = []

    if len(current_row) >= 1:
        yield current_row


