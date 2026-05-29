import pandas as pd


def get_tables_dict(constraints_dict, dtypes):
    """Identify groups of indicators (census) belonging to the same table
    We will index each table as a frozen set
    An empty set identifies the total population, the top-most marginal

    To visualize the table we need the complete set fo categories for each variable
    We can find these in the schema or in the dataframe with the data wich have been validated with such an schema"""

    tables = {}
    for col, var_dict in constraints_dict.items():
        var_set = frozenset(var_dict.keys())
        if var_set not in tables:
            tables[var_set] = {"Vars": {}, "Cells": {}}
            for var in var_set:
                tables[var_set]["Vars"][var] = tuple(dtypes[var].categories)
        tables[var_set]["Cells"][col] = constraints_dict[col]
        # Check is variables match
        for var, cats in tables[var_set]["Cells"][col].items():
            assert set(cats).issubset(set(tables[var_set]["Vars"][var])), (
                var,
                cats,
                tables[var_set]["Vars"][var],
            )
    return tables


def create_cont_table(table, group=False):
    var_dict = table["Vars"]
    cells_dict = table["Cells"]

    # Create index and columns index
    # Always choose as columns the variable with the most categories
    var_list = sorted(list(var_dict.keys()), key=lambda x: len(var_dict[x]))
    col_var = var_list[-1]
    columns = pd.Index(var_dict[col_var], name=col_var)

    # The index is all other variables, and the available columns as the innermost index
    index_vars = var_list[:-1]
    indices_arr = [var_dict[var] for var in index_vars]
    indices_arr.append(list(cells_dict.keys()))
    index = pd.MultiIndex.from_product(indices_arr, names=index_vars + ["Indicator"])

    # The dataframe
    table_df = pd.DataFrame(index=index, columns=columns)

    # Fill the dataframe a columns at a time
    for col, col_dict in cells_dict.items():
        col_idxs = col_dict[col_var]
        row_idxs = tuple([col_dict[var] for var in index.names[:-1]] + [col])
        table_df.loc[row_idxs, col_idxs] = col

    table_df = table_df.dropna(how="all").fillna("")
    if group:
        table_df = table_df.groupby(var_list[:-1]).agg(
            lambda x: sorted(list(set(x) - set([""])))
        )
    return table_df
