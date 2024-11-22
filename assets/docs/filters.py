def exclude_commonx_members(member, name):
    print(member, name)
    import common
    return not hasattr(common, name)

