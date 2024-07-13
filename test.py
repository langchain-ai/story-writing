def transform_titles_into_options(titles):
    name_counts = {}
    for name in set(titles):
        name_counts[name] = titles.count(name)

    # Transform names with numbered suffixes
    transformed_titles = []
    for name in titles[::-1]:
        count = name_counts[name]
        if count > 1 or titles.count(name) > 1:
            transformed_titles.append(f"{name} #{count}")
        else:
            transformed_titles.append(name)
        name_counts[name] -= 1

    return transformed_titles[::-1]


print(transform_titles_into_options(['a','b','a','c']))