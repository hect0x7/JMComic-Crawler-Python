def exclude_commonx_members(member, name):
    print(member, name)
    import common
    return hasattr(common, name)

