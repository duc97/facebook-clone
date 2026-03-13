from __future__ import annotations

import pytest
import strawberry
from strawberry.schema import Schema
from fb.presentation.graphql.types.post import PostType
from fb.presentation.graphql.inputs.post import CreatePostInput, UpdatePostInput, DeletePostInput
from fb.presentation.graphql.mutations.post import PostMutation
from fb.presentation.graphql.queries.post import PostQuery


class TestPostGraphQLSchema:
    def test_post_type_introspection(self) -> None:
        """Test that PostType has all required fields"""
        post_type_fields = PostType.__strawberry_definition__.fields
        field_names = [field.python_name for field in post_type_fields]

        expected_fields = [
            "id",
            "author_id",
            "content",
            "media_urls",
            "like_count",
            "comment_count",
            "is_published",
        ]

        for field in expected_fields:
            assert field in field_names

    def test_create_post_input_introspection(self) -> None:
        """Test that CreatePostInput has all required fields"""
        input_fields = CreatePostInput.__strawberry_definition__.fields
        field_names = [field.python_name for field in input_fields]

        expected_fields = ["content", "media_urls"]
        for field in expected_fields:
            assert field in field_names

    def test_update_post_input_introspection(self) -> None:
        """Test that UpdatePostInput has all required fields"""
        input_fields = UpdatePostInput.__strawberry_definition__.fields
        field_names = [field.python_name for field in input_fields]

        expected_fields = ["post_id", "content"]
        for field in expected_fields:
            assert field in field_names

    def test_delete_post_input_introspection(self) -> None:
        """Test that DeletePostInput has all required fields"""
        input_fields = DeletePostInput.__strawberry_definition__.fields
        field_names = [field.python_name for field in input_fields]

        expected_fields = ["post_id"]
        for field in expected_fields:
            assert field in field_names

    def test_schema_can_be_created_with_post_types(self) -> None:
        """Test that a GraphQL schema can be created with Post types"""
        @strawberry.type
        class Query:
            @strawberry.field
            def hello(self) -> str:
                return "Hello"

        @strawberry.type
        class Mutation:
            @strawberry.field
            def placeholder(self) -> str:
                return "placeholder"

        schema = Schema(query=Query, mutation=Mutation)

        # Should not raise any errors
        assert schema is not None