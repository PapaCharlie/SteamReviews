$('#game-searchbar').autocomplete({
    lookup: {{ app_id_to_name | safe }},
    triggerSelectOnValidInput: false,
    onSelect: function(suggestion) {
        window.location = "/?app_id=" + suggestion.data
    }
});
