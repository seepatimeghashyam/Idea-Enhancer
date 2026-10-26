import arxiv

def search_papers(project_idea, max_results=5):
    client = arxiv.Client()

    search = arxiv.Search(
    query=project_idea.replace(" ", " AND "),
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    papers = []

    for result in client.results(search):
        papers.append({
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "abstract": result.summary,
            "published": result.published.strftime("%Y-%m-%d"),
            "url": result.entry_id
        })

    return papers


if __name__ == "__main__":
    idea = input("Enter your project idea: ")

    try:
        papers = search_papers(idea)

        if not papers:
            print("No relevant papers found.")
        else:
            for i, paper in enumerate(papers, start=1):
                print(f"\n--- Paper {i} ---")
                print("Title:", paper["title"])
                print("Authors:", ", ".join(paper["authors"]))
                print("Published:", paper["published"])
                print("Abstract:", paper["abstract"])
                print("Link:", paper["url"])

    except Exception as e:
        print("Error while searching papers:", e)