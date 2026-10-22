#include <stdio.h>

/* Safely compute the sum of two 64-bit integers without 32-bit overflow. */
static long long add_integers(long long lhs, long long rhs) {
    return lhs + rhs;
}

/* Entry point: read two integers from stdin and print their 64-bit sum. */
int main(void) {
    long long lhs = 0;
    long long rhs = 0;
    if (scanf("%lld %lld", &lhs, &rhs) != 2) {
        return 1;
    }
    printf("%lld\n", add_integers(lhs, rhs));
    return 0;
}
